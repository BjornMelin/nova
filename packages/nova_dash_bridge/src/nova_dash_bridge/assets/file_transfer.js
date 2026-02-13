(function () {
  "use strict";

  function setDashProps(id, props) {
    if (!id) return;
    if (!window.dash_clientside) return;
    if (typeof window.dash_clientside.set_props !== "function") return;
    window.dash_clientside.set_props(id, props);
  }

  function byteToHex(byte) {
    return (byte + 0x100).toString(16).slice(1);
  }

  function formatUuidFromBytes(bytes) {
    bytes[6] = (bytes[6] & 0x0f) | 0x40;
    bytes[8] = (bytes[8] & 0x3f) | 0x80;
    var hex = "";
    for (var idx = 0; idx < bytes.length; idx += 1) {
      hex += byteToHex(bytes[idx]);
    }
    return (
      hex.slice(0, 8) +
      "-" +
      hex.slice(8, 12) +
      "-" +
      hex.slice(12, 16) +
      "-" +
      hex.slice(16, 20) +
      "-" +
      hex.slice(20, 32)
    );
  }

  function safeUuid() {
    if (window.crypto && typeof window.crypto.randomUUID === "function") {
      return window.crypto.randomUUID();
    }
    if (window.crypto && typeof window.crypto.getRandomValues === "function") {
      var secureBytes = new Uint8Array(16);
      window.crypto.getRandomValues(secureBytes);
      return formatUuidFromBytes(secureBytes);
    }
    var fallbackBytes = new Uint8Array(16);
    for (var idx = 0; idx < fallbackBytes.length; idx += 1) {
      fallbackBytes[idx] = Math.floor(Math.random() * 256);
    }
    return formatUuidFromBytes(fallbackBytes);
  }

  function getSessionId() {
    var node = document.getElementById("file-transfer-session-id");
    if (node && typeof node.textContent === "string") {
      var value = node.textContent.trim();
      if (value) return value;
    }
    return safeUuid();
  }

  async function postJson(url, payload, headers) {
    var timeoutMs = 30000;
    var controller = new AbortController();
    var timeoutId = window.setTimeout(function () {
      controller.abort();
    }, timeoutMs);
    var mergedHeaders = { "Content-Type": "application/json" };
    if (headers && typeof headers === "object") {
      Object.keys(headers).forEach(function (key) {
        mergedHeaders[key] = headers[key];
      });
    }
    try {
      var response = await fetch(url, {
        method: "POST",
        headers: mergedHeaders,
        credentials: "same-origin",
        body: JSON.stringify(payload),
        signal: controller.signal,
      });
      var data = await response.json().catch(function () {
        return {};
      });
      if (!response.ok) {
        var message = "HTTP " + response.status;
        if (data && data.error && data.error.message) {
          message = data.error.message;
        }
        throw new Error(message);
      }
      return data;
    } catch (error) {
      if (error && error.name === "AbortError") {
        throw new Error("request timed out after " + timeoutMs + "ms");
      }
      throw error;
    } finally {
      window.clearTimeout(timeoutId);
    }
  }

  async function getJson(url, headers) {
    var timeoutMs = 30000;
    var controller = new AbortController();
    var timeoutId = window.setTimeout(function () {
      controller.abort();
    }, timeoutMs);
    var mergedHeaders = {};
    if (headers && typeof headers === "object") {
      Object.keys(headers).forEach(function (key) {
        mergedHeaders[key] = headers[key];
      });
    }
    try {
      var response = await fetch(url, {
        method: "GET",
        headers: mergedHeaders,
        credentials: "same-origin",
        signal: controller.signal,
      });
      var data = await response.json().catch(function () {
        return {};
      });
      if (!response.ok) {
        var message = "HTTP " + response.status;
        if (data && data.error && data.error.message) {
          message = data.error.message;
        }
        throw new Error(message);
      }
      return data;
    } catch (error) {
      if (error && error.name === "AbortError") {
        throw new Error("request timed out after " + timeoutMs + "ms");
      }
      throw error;
    } finally {
      window.clearTimeout(timeoutId);
    }
  }

  function setProgress(storeId, percent, message) {
    setDashProps(storeId, {
      data: { percent: percent, message: message || "" },
    });
  }

  function setResult(storeId, payload) {
    setDashProps(storeId, { data: payload });
  }

  async function putWithTimeout(url, options, timeoutMs, timeoutErrorMessage) {
    var controller = new AbortController();
    var timeoutId = window.setTimeout(function () {
      controller.abort();
    }, timeoutMs);
    try {
      return await fetch(url, {
        method: "PUT",
        signal: controller.signal,
        ...options,
      });
    } catch (error) {
      if (error && error.name === "AbortError") {
        throw new Error(timeoutErrorMessage);
      }
      throw error;
    } finally {
      window.clearTimeout(timeoutId);
    }
  }

  async function putObject(url, file, contentType) {
    var timeoutMs = 300000;
    var response = await putWithTimeout(
      url,
      {
        headers: {
          "Content-Type": contentType || "application/octet-stream",
        },
        body: file,
      },
      timeoutMs,
      "upload request timed out after " + timeoutMs + "ms"
    );
    if (!response.ok) {
      throw new Error("upload failed (HTTP " + response.status + ")");
    }
    return response.headers.get("ETag");
  }

  async function putPart(url, blob) {
    var timeoutMs = 300000;
    var response = await putWithTimeout(
      url,
      { body: blob },
      timeoutMs,
      "part upload timed out after " + timeoutMs + "ms"
    );
    if (!response.ok) {
      throw new Error("part upload failed (HTTP " + response.status + ")");
    }
    return response.headers.get("ETag") || "";
  }

  function sleep(ms) {
    return new Promise(function (resolve) {
      window.setTimeout(resolve, ms);
    });
  }

  async function uploadMultipart(config, file, initiated, sessionId) {
    var base = config.transfersEndpointBase;
    var key = initiated.key;
    var uploadId = initiated.upload_id;
    var partSize = parseInt(initiated.part_size_bytes, 10);
    if (!Number.isFinite(partSize) || partSize <= 0) {
      throw new Error(
        "Invalid part_size_bytes: must be a positive integer"
      );
    }
    var maxConcurrency = Math.max(1, parseInt(config.maxConcurrency, 10) || 4);
    var totalParts = Math.ceil(file.size / partSize);
    var completeParts = [];
    var uploadedBytes = 0;

    async function uploadSinglePart(partNumber, url) {
      var start = (partNumber - 1) * partSize;
      var end = Math.min(file.size, start + partSize);
      var blob = file.slice(start, end);
      var attempt = 0;
      while (attempt < 3) {
        attempt += 1;
        try {
          var etag = await putPart(url, blob);
          uploadedBytes += blob.size;
          var pct = Math.floor((uploadedBytes / file.size) * 100);
          setProgress(config.progressStoreId, pct, "Uploading… " + pct + "%");
          return { part_number: partNumber, etag: etag };
        } catch (error) {
          if (attempt >= 3) throw error;
          await sleep(250 * attempt);
        }
      }
    }

    try {
      var batchSize = 50;
      for (var startPart = 1; startPart <= totalParts; startPart += batchSize) {
        var endPart = Math.min(totalParts, startPart + batchSize - 1);
        var partNumbers = [];
        for (var p = startPart; p <= endPart; p += 1) partNumbers.push(p);

        var sign = await postJson(base + "/uploads/sign-parts", {
          key: key,
          upload_id: uploadId,
          part_numbers: partNumbers,
          session_id: sessionId,
        });

        var queue = partNumbers.slice();
        var workers = [];
        for (var w = 0; w < maxConcurrency; w += 1) {
          workers.push(
            (async function () {
              while (queue.length) {
                var partNumber = queue.shift();
                var signedUrl = sign.urls[String(partNumber)];
                if (!signedUrl) {
                  throw new Error("missing signed URL for part " + partNumber);
                }
                var completed = await uploadSinglePart(partNumber, signedUrl);
                completeParts.push(completed);
              }
            })()
          );
        }
        await Promise.all(workers);
      }

      completeParts.sort(function (a, b) {
        return a.part_number - b.part_number;
      });
      await postJson(base + "/uploads/complete", {
        key: key,
        upload_id: uploadId,
        parts: completeParts,
        session_id: sessionId,
      });
      return { key: key, uploadId: uploadId };
    } catch (error) {
      if (uploadId) {
        try {
          await postJson(base + "/uploads/abort", {
            key: key,
            upload_id: uploadId,
            session_id: sessionId,
          });
        } catch (_abortError) {
          // Best-effort cleanup; preserve the original upload failure.
        }
      }
      throw error;
    }
  }

  function buildUploadResult(file, initiated, contentType, sessionId) {
    return {
      bucket: initiated.bucket,
      key: initiated.key,
      filename: file.name,
      size_bytes: file.size,
      content_type: contentType,
      session_id: sessionId,
    };
  }

  function shouldUseAsyncJobs(config, fileSize) {
    return (
      config.asyncJobsEnabled &&
      Number.isFinite(config.asyncJobMinBytes) &&
      fileSize >= config.asyncJobMinBytes
    );
  }

  async function enqueueAsyncJob(config, uploadResult) {
    var idempotencyKey =
      "job-enqueue:" + uploadResult.session_id + ":" + uploadResult.key;
    var enqueuePayload = {
      job_type: config.asyncJobType,
      payload: {
        bucket: uploadResult.bucket,
        key: uploadResult.key,
        filename: uploadResult.filename,
        size_bytes: uploadResult.size_bytes,
        content_type: uploadResult.content_type,
      },
      session_id: uploadResult.session_id,
    };
    return postJson(
      config.jobsEndpointBase + "/enqueue",
      enqueuePayload,
      { "Idempotency-Key": idempotencyKey }
    );
  }

  async function pollAsyncJob(config, jobId, sessionId) {
    var startedMs = Date.now();
    var pollHeaders = {};
    if (typeof sessionId === "string" && sessionId) {
      pollHeaders["X-Session-Id"] = sessionId;
    }
    while (true) {
      var response = await getJson(
        config.jobsEndpointBase + "/" + encodeURIComponent(jobId),
        pollHeaders
      );
      var job = response && response.job ? response.job : {};
      var status = job.status || "";
      if (
        status === "succeeded" ||
        status === "failed" ||
        status === "canceled"
      ) {
        return job;
      }
      if (Date.now() - startedMs > config.asyncJobTimeoutMs) {
        throw new Error(
          "job status polling timed out after " +
            config.asyncJobTimeoutMs +
            "ms"
        );
      }
      await sleep(config.asyncJobPollIntervalMs);
    }
  }

  async function maybePresignExportDownload(config, uploadResult, job) {
    var result = job && typeof job.result === "object" ? job.result : null;
    if (!result) return null;
    if (typeof result.export_key !== "string" || !result.export_key) {
      return null;
    }
    var requestPayload = {
      key: result.export_key,
      session_id: uploadResult.session_id,
    };
    if (
      typeof result.download_filename === "string" &&
      result.download_filename
    ) {
      requestPayload.filename = result.download_filename;
    }
    var response = await postJson(
      config.transfersEndpointBase + "/downloads/presign",
      requestPayload
    );
    if (response && typeof response.url === "string" && response.url) {
      return {
        key: result.export_key,
        url: response.url,
        expires_in_seconds: response.expires_in_seconds,
      };
    }
    return null;
  }

  async function handleUpload(config, file) {
    var sessionId = getSessionId();
    var contentType = file.type || "application/octet-stream";
    setProgress(config.progressStoreId, 0, "Preparing upload…");

    var initiated = await postJson(
      config.transfersEndpointBase + "/uploads/initiate",
      {
        filename: file.name,
        content_type: contentType,
        size_bytes: file.size,
        session_id: sessionId,
      }
    );

    var uploadResult = null;
    if (initiated.strategy === "single") {
      await putObject(initiated.url, file, contentType);
      uploadResult = buildUploadResult(
        file,
        initiated,
        contentType,
        sessionId
      );
    } else if (initiated.strategy === "multipart") {
      await uploadMultipart(config, file, initiated, sessionId);
      uploadResult = buildUploadResult(
        file,
        initiated,
        contentType,
        sessionId
      );
    } else {
      throw new Error("unknown strategy");
    }

    if (!uploadResult) {
      throw new Error("upload did not produce a result payload");
    }
    setProgress(config.progressStoreId, 100, "Upload complete");

    if (!shouldUseAsyncJobs(config, file.size)) {
      return uploadResult;
    }

    setProgress(
      config.progressStoreId,
      100,
      "Upload complete. Queueing processing job…"
    );
    var enqueued = await enqueueAsyncJob(config, uploadResult);
    if (!enqueued || typeof enqueued.job_id !== "string" || !enqueued.job_id) {
      throw new Error("jobs enqueue response did not include a job_id");
    }

    setProgress(
      config.progressStoreId,
      100,
      "Processing in background. Waiting for job result…"
    );
    var job = await pollAsyncJob(
      config,
      enqueued.job_id,
      uploadResult.session_id
    );
    if (job.status === "failed" || job.status === "canceled") {
      var errorMessage =
        typeof job.error === "string" && job.error
          ? job.error
          : "background processing " + job.status;
      throw new Error(errorMessage);
    }

    var download = await maybePresignExportDownload(
      config,
      uploadResult,
      job
    );
    setProgress(config.progressStoreId, 100, "Processing complete");
    return {
      ...uploadResult,
      job_id: enqueued.job_id,
      job_status: job.status,
      job_result: job.result || null,
      download: download,
    };
  }

  function attachUploader(root) {
    if (!root || root.dataset.bound === "true") return;
    var dropzone = document.getElementById(root.dataset.dropzoneId);
    if (!dropzone) return;

    var input = document.getElementById(root.dataset.inputId);
    if (!input) {
      input = document.createElement("input");
      input.type = "file";
      input.style.display = "none";
      if (root.dataset.inputId) {
        input.id = root.dataset.inputId;
      }
      if (root.dataset.accept) {
        input.setAttribute("accept", root.dataset.accept);
      }
      if (root.dataset.multiple === "true") {
        input.multiple = true;
      }
      root.appendChild(input);
    }

    var config = {
      transfersEndpointBase:
        root.dataset.transfersEndpointBase || "/api/transfers",
      jobsEndpointBase: root.dataset.jobsEndpointBase || "/api/jobs",
      maxConcurrency: root.dataset.maxConcurrency || "4",
      maxBytes: parseInt(root.dataset.maxBytes || "0", 10),
      resultStoreId: root.dataset.resultStoreId || "",
      progressStoreId: root.dataset.progressStoreId || "",
      asyncJobsEnabled: root.dataset.asyncJobsEnabled === "true",
      asyncJobType: root.dataset.asyncJobType || "process_upload",
      asyncJobMinBytes: parseInt(root.dataset.asyncJobMinBytes || "0", 10),
      asyncJobPollIntervalMs: Math.max(
        100,
        parseInt(root.dataset.asyncJobPollIntervalMs || "2000", 10) || 2000
      ),
      asyncJobTimeoutMs: Math.max(
        1000,
        parseInt(root.dataset.asyncJobTimeoutMs || "900000", 10) || 900000
      ),
    };
    var allowMultiple = root.dataset.multiple === "true";

    async function handleFiles(files) {
      if (!files || !files.length) return;
      var selectedFiles = Array.prototype.slice.call(files);
      var filesToUpload = allowMultiple
        ? selectedFiles
        : selectedFiles.slice(0, 1);
      var results = [];

      for (var idx = 0; idx < filesToUpload.length; idx += 1) {
        var file = filesToUpload[idx];
        if (config.maxBytes > 0 && file.size > config.maxBytes) {
          setProgress(
            config.progressStoreId,
            0,
            "Upload failed: file exceeds max size"
          );
          setResult(config.resultStoreId, null);
          return;
        }
        try {
          results.push(await handleUpload(config, file));
        } catch (error) {
          var message = error && error.message ? error.message : String(error);
          setProgress(config.progressStoreId, 0, "Upload failed: " + message);
          setResult(config.resultStoreId, null);
          return;
        }
      }
      setResult(config.resultStoreId, allowMultiple ? results : results[0]);
    }

    function handleFilesRejection(error) {
      var message = error && error.message ? error.message : String(error);
      setProgress(config.progressStoreId, 0, "Upload failed: " + message);
      setResult(config.resultStoreId, null);
      console.error("file_transfer.handle_files_failed", error);
    }

    dropzone.addEventListener("click", function () {
      input.click();
    });
    dropzone.addEventListener("keydown", function (event) {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        input.click();
      }
    });
    dropzone.addEventListener("dragover", function (event) {
      event.preventDefault();
      dropzone.classList.add("nova-dropzone-active");
    });
    dropzone.addEventListener("dragleave", function (event) {
      event.preventDefault();
      dropzone.classList.remove("nova-dropzone-active");
    });
    dropzone.addEventListener("drop", function (event) {
      event.preventDefault();
      dropzone.classList.remove("nova-dropzone-active");
      handleFiles(event.dataTransfer ? event.dataTransfer.files : null).catch(
        handleFilesRejection
      );
    });
    input.addEventListener("change", function (event) {
      handleFiles(event.target ? event.target.files : null).catch(
        handleFilesRejection
      );
    });

    root.dataset.bound = "true";
  }

  function scan() {
    var nodes = document.querySelectorAll(".nova-uploader");
    nodes.forEach(attachUploader);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", scan);
  } else {
    scan();
  }

  var scanTimeout = null;
  var observer = new MutationObserver(function () {
    if (scanTimeout !== null) {
      window.clearTimeout(scanTimeout);
    }
    scanTimeout = window.setTimeout(function () {
      scanTimeout = null;
      scan();
    }, 50);
  });
  observer.observe(document.documentElement, {
    childList: true,
    subtree: true,
  });
})();
