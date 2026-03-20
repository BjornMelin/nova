(function () {
  "use strict";

  function setDashProps(id, props) {
    if (!id) return;
    if (!window.dash_clientside) return;
    if (typeof window.dash_clientside.set_props !== "function") return;
    window.dash_clientside.set_props(id, props);
  }

  function getAuthorizationHeader(config) {
    var node = document.getElementById(config.authHeaderElementId || "");
    if (node && typeof node.textContent === "string") {
      var value = node.textContent.trim();
      if (value) return value;
    }
    return "";
  }

  function authorizedHeaders(config, headers) {
    var merged = {};
    if (headers && typeof headers === "object") {
      Object.keys(headers).forEach(function (key) {
        merged[key] = headers[key];
      });
    }
    var authorizationHeader = getAuthorizationHeader(config);
    if (authorizationHeader) {
      merged.Authorization = authorizationHeader;
    }
    return merged;
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

  function multipartStateStorageKey(config, file) {
    var resumeNamespace = String(config.resumeNamespace || "");
    return [
      "nova-multipart-upload",
      resumeNamespace,
      config.transfersEndpointBase || "/v1/transfers",
      file.name || "",
      String(file.size || 0),
      String(file.lastModified || 0),
    ].join(":");
  }

  function loadMultipartState(storageKey) {
    if (!storageKey) return null;
    try {
      var storage = window.localStorage;
      if (!storage) return null;
      var raw = storage.getItem(storageKey);
      if (!raw) return null;
      var parsed = JSON.parse(raw);
      if (!parsed || typeof parsed !== "object") return null;
      return parsed;
    } catch (_error) {
      return null;
    }
  }

  function persistMultipartState(storageKey, state) {
    if (!storageKey) return;
    try {
      var storage = window.localStorage;
      if (!storage) return;
      storage.setItem(storageKey, JSON.stringify(state));
    } catch (_error) {
      // Best-effort persistence only.
    }
  }

  function clearMultipartState(storageKey) {
    if (!storageKey) return;
    try {
      var storage = window.localStorage;
      if (!storage) return;
      storage.removeItem(storageKey);
    } catch (_error) {
      // Best-effort cleanup only.
    }
  }

  function partSizeForNumber(fileSize, partSize, partNumber) {
    var start = (partNumber - 1) * partSize;
    var end = Math.min(fileSize, start + partSize);
    return Math.max(0, end - start);
  }

  async function uploadMultipart(config, file, initiated) {
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
    var configuredBatchSize = parseInt(config.signBatchSize || "0", 10);
    var batchSize = configuredBatchSize > 0
      ? configuredBatchSize
      : Math.min(16, Math.max(1, maxConcurrency * 2));
    var totalParts = Math.ceil(file.size / partSize);
    var completeParts = [];
    var uploadedBytes = 0;
    var storageKey = multipartStateStorageKey(config, file);
    persistMultipartState(storageKey, {
      bucket: initiated.bucket,
      key: key,
      upload_id: uploadId,
      part_size_bytes: partSize,
    });

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
      var completedByPartNumber = {};
      var introspected = await postJson(
        base + "/uploads/introspect",
        {
          key: key,
          upload_id: uploadId,
        },
        authorizedHeaders(config)
      );
      var existingParts =
        introspected && Array.isArray(introspected.parts)
          ? introspected.parts
          : [];
      existingParts.forEach(function (part) {
        var partNumber = parseInt(part.part_number, 10);
        if (!Number.isFinite(partNumber) || partNumber <= 0) return;
        completedByPartNumber[partNumber] = {
          part_number: partNumber,
          etag: part.etag || "",
        };
        uploadedBytes += partSizeForNumber(file.size, partSize, partNumber);
      });
      if (uploadedBytes > 0) {
        var resumedPct = Math.floor((uploadedBytes / file.size) * 100);
        setProgress(
          config.progressStoreId,
          resumedPct,
          "Resuming upload… " + resumedPct + "%"
        );
      }

      var pendingPartNumbers = [];
      for (var pending = 1; pending <= totalParts; pending += 1) {
        if (!completedByPartNumber[pending]) {
          pendingPartNumbers.push(pending);
        }
      }

      for (var startIndex = 0; startIndex < pendingPartNumbers.length; startIndex += batchSize) {
        var partNumbers = pendingPartNumbers.slice(
          startIndex,
          startIndex + batchSize
        );

        var sign = await postJson(
          base + "/uploads/sign-parts",
          {
            key: key,
            upload_id: uploadId,
            part_numbers: partNumbers,
          },
          authorizedHeaders(config)
        );

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
                completedByPartNumber[partNumber] = completed;
              }
            })()
          );
        }
        await Promise.all(workers);
      }

      completeParts = Object.keys(completedByPartNumber).map(function (keyName) {
        return completedByPartNumber[Number(keyName)];
      });
      completeParts.sort(function (a, b) {
        return a.part_number - b.part_number;
      });
      await postJson(
        base + "/uploads/complete",
        {
          key: key,
          upload_id: uploadId,
          parts: completeParts,
        },
        authorizedHeaders(config)
      );
      clearMultipartState(storageKey);
      return { key: key, uploadId: uploadId };
    } catch (error) {
      throw error;
    }
  }

  function buildUploadResult(file, initiated, contentType) {
    return {
      bucket: initiated.bucket,
      key: initiated.key,
      filename: file.name,
      size_bytes: file.size,
      content_type: contentType,
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
    var jobsBase = config.jobsEndpointBase.replace(/\/$/, "");
    var idempotencyKey =
      "job-enqueue:" + uploadResult.bucket + ":" + uploadResult.key;
    var enqueuePayload = {
      job_type: config.asyncJobType,
      payload: {
        bucket: uploadResult.bucket,
        key: uploadResult.key,
        filename: uploadResult.filename,
        size_bytes: uploadResult.size_bytes,
        content_type: uploadResult.content_type,
      },
    };
    return postJson(
      jobsBase,
      enqueuePayload,
      authorizedHeaders(config, { "Idempotency-Key": idempotencyKey })
    );
  }

  async function pollAsyncJob(config, jobId) {
    var startedMs = Date.now();
    var jobsBase = config.jobsEndpointBase.replace(/\/$/, "");
    while (true) {
      var response = await getJson(
        jobsBase + "/" + encodeURIComponent(jobId),
        authorizedHeaders(config)
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
    };
    if (
      typeof result.download_filename === "string" &&
      result.download_filename
    ) {
      requestPayload.filename = result.download_filename;
    }
    var response = await postJson(
      config.transfersEndpointBase + "/downloads/presign",
      requestPayload,
      authorizedHeaders(config)
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

  function isMultipartNotFoundError(error) {
    return (
      error &&
      typeof error.message === "string" &&
      error.message.indexOf("multipart upload was not found") !== -1
    );
  }

  function isUploadObjectMissingError(error) {
    return (
      error &&
      typeof error.message === "string" &&
      (error.message.indexOf("upload object not found") !== -1 ||
        error.message.indexOf("source upload object not found") !== -1 ||
        error.message.indexOf("HTTP 404") !== -1)
    );
  }

  async function checkUploadObjectExists(config, key, filename) {
    var requestPayload = {
      key: key,
    };
    if (typeof filename === "string" && filename) {
      requestPayload.filename = filename;
    }
    try {
      await postJson(
        config.transfersEndpointBase + "/downloads/presign",
        requestPayload,
        authorizedHeaders(config)
      );
      return true;
    } catch (error) {
      if (isUploadObjectMissingError(error)) {
        return false;
      }
      throw error;
    }
  }

  async function handleUpload(config, file) {
    var contentType = file.type || "application/octet-stream";
    var storageKey = multipartStateStorageKey(config, file);
    var storedMultipartState = loadMultipartState(storageKey);
    setProgress(config.progressStoreId, 0, "Preparing upload…");

    var initiated = null;
    var resumedMultipart =
      storedMultipartState &&
      typeof storedMultipartState.upload_id === "string" &&
      typeof storedMultipartState.key === "string" &&
      typeof storedMultipartState.bucket === "string" &&
      Number.isFinite(parseInt(storedMultipartState.part_size_bytes, 10));
    if (resumedMultipart) {
      initiated = {
        strategy: "multipart",
        bucket: storedMultipartState.bucket,
        key: storedMultipartState.key,
        upload_id: storedMultipartState.upload_id,
        part_size_bytes: parseInt(storedMultipartState.part_size_bytes, 10),
        expires_in_seconds: 0,
      };
      setProgress(config.progressStoreId, 0, "Resuming upload…");
    } else {
      initiated = await postJson(
        config.transfersEndpointBase + "/uploads/initiate",
        {
          filename: file.name,
          content_type: contentType,
          size_bytes: file.size,
        },
        authorizedHeaders(config)
      );
    }

    var uploadResult = null;
    if (initiated.strategy === "single") {
      await putObject(initiated.url, file, contentType);
      clearMultipartState(storageKey);
      uploadResult = buildUploadResult(
        file,
        initiated,
        contentType
      );
    } else if (initiated.strategy === "multipart") {
      try {
        await uploadMultipart(config, file, initiated);
      } catch (error) {
        var resumeMissingMultipart =
          resumedMultipart && isMultipartNotFoundError(error);
        if (resumeMissingMultipart) {
          var introspectMissingMultipart = false;
          try {
            await postJson(
              config.transfersEndpointBase + "/uploads/introspect",
              {
                key: initiated.key,
                upload_id: initiated.upload_id,
              },
              authorizedHeaders(config)
            );
          } catch (introspectError) {
            if (!isMultipartNotFoundError(introspectError)) {
              throw introspectError;
            }
            introspectMissingMultipart = true;
          }
          if (!introspectMissingMultipart) {
            throw error;
          }
          var uploadObjectExists = await checkUploadObjectExists(
            config,
            initiated.key,
            file.name
          );
          if (uploadObjectExists) {
            throw new Error(
              "multipart upload completion is ambiguous; upload object already exists"
            );
          }
          clearMultipartState(storageKey);
          storageKey = multipartStateStorageKey(config, file);
          initiated = await postJson(
            config.transfersEndpointBase + "/uploads/initiate",
            {
              filename: file.name,
              content_type: contentType,
              size_bytes: file.size,
            },
            authorizedHeaders(config)
          );
          if (initiated.strategy === "single") {
            await putObject(initiated.url, file, contentType);
            clearMultipartState(storageKey);
          } else if (initiated.strategy === "multipart") {
            await uploadMultipart(config, file, initiated);
          } else {
            throw new Error("unknown strategy");
          }
        } else {
          // Keep resumable state for transient failures and retry paths.
          // We only clear stored state in verified missing-multipart scenarios.
          throw error;
        }
      }
      uploadResult = buildUploadResult(
        file,
        initiated,
        contentType
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
      enqueued.job_id
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
        root.dataset.transfersEndpointBase || "/v1/transfers",
      jobsEndpointBase: root.dataset.jobsEndpointBase || "/v1/jobs",
      authHeaderElementId: root.dataset.authHeaderElementId || "",
      maxConcurrency: root.dataset.maxConcurrency || "4",
      signBatchSize: root.dataset.signBatchSize || "",
      resumeNamespace: root.dataset.resumeNamespace || "",
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
