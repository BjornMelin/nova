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
        body: JSON.stringify(payload),
        credentials: "omit",
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
        credentials: "omit",
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
        credentials: "omit",
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

  async function putObject(url, file, contentType, extraHeaders) {
    var timeoutMs = 300000;
    var headers = {
      "Content-Type": contentType || "application/octet-stream",
    };
    if (extraHeaders && typeof extraHeaders === "object") {
      Object.keys(extraHeaders).forEach(function (key) {
        headers[key] = extraHeaders[key];
      });
    }
    var response = await putWithTimeout(
      url,
      {
        headers: headers,
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

  async function putPart(url, blob, extraHeaders) {
    var timeoutMs = 300000;
    var headers = {};
    if (extraHeaders && typeof extraHeaders === "object") {
      Object.keys(extraHeaders).forEach(function (key) {
        headers[key] = extraHeaders[key];
      });
    }
    var response = await putWithTimeout(
      url,
      { body: blob, headers: headers },
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

  function clampPositiveInt(value, fallback, maximum) {
    if (!Number.isFinite(value) || value <= 0) {
      return fallback;
    }
    return Math.min(maximum, Math.max(1, Math.floor(value)));
  }

  function isResumableStateExpired(state) {
    if (!state || typeof state.resumable_until !== "string" || !state.resumable_until) {
      return false;
    }
    var resumableUntilMs = Date.parse(state.resumable_until);
    return Number.isFinite(resumableUntilMs) && resumableUntilMs <= Date.now();
  }

  function capabilitiesEndpoint(config) {
    var base = String(config.transfersEndpointBase || "/v1/transfers").replace(/\/$/, "");
    return base.replace(/\/v1\/transfers$/, "") + "/v1/capabilities/transfers";
  }

  function buildCapabilitiesUrl(config) {
    var url = capabilitiesEndpoint(config);
    var params = [];
    if (config.workloadClass) {
      params.push("workload_class=" + encodeURIComponent(config.workloadClass));
    }
    if (config.policyHint) {
      params.push("policy_hint=" + encodeURIComponent(config.policyHint));
    }
    if (!params.length) {
      return url;
    }
    return url + "?" + params.join("&");
  }

  async function fetchTransferCapabilities(config) {
    return await getJson(buildCapabilitiesUrl(config), authorizedHeaders(config));
  }

  async function sha256Base64FromBlob(blob) {
    if (!window.crypto || !window.crypto.subtle) {
      throw new Error("SHA-256 checksum requires Web Crypto support");
    }
    var buffer = await blob.arrayBuffer();
    var digest = await window.crypto.subtle.digest("SHA-256", buffer);
    var bytes = new Uint8Array(digest);
    var binary = "";
    for (var index = 0; index < bytes.length; index += 1) {
      binary += String.fromCharCode(bytes[index]);
    }
    return window.btoa(binary);
  }

  function shouldApplyChecksum(config, capabilities) {
    if (!capabilities || capabilities.checksum_algorithm !== "SHA256") {
      return false;
    }
    if (capabilities.checksum_mode === "required") {
      return true;
    }
    return config.checksumPreference === "standard" || config.checksumPreference === "strict";
  }

  function buildInitiatePayload(config, file, contentType, extra) {
    var payload = {
      filename: file.name,
      content_type: contentType,
      size_bytes: file.size,
    };
    if (config.workloadClass) {
      payload.workload_class = config.workloadClass;
    }
    if (config.policyHint) {
      payload.policy_hint = config.policyHint;
    }
    if (config.checksumPreference) {
      payload.checksum_preference = config.checksumPreference;
    }
    if (extra && extra.checksumValue) {
      payload.checksum_value = extra.checksumValue;
    }
    return payload;
  }

  async function uploadMultipart(config, file, initiated, storedMultipartState) {
    var base = config.transfersEndpointBase;
    var key = initiated.key;
    var uploadId = initiated.upload_id;
    var partSize = parseInt(initiated.part_size_bytes, 10);
    if (!Number.isFinite(partSize) || partSize <= 0) {
      throw new Error(
        "Invalid part_size_bytes: must be a positive integer"
      );
    }
    var hintedConcurrency = parseInt(initiated.max_concurrency_hint, 10);
    var maxConcurrency = Number.isFinite(hintedConcurrency) && hintedConcurrency > 0
      ? clampPositiveInt(hintedConcurrency, 1, 32)
      : clampPositiveInt(
        parseInt(config.maxConcurrency, 10),
        4,
        32
      );
    var configuredBatchSize = clampPositiveInt(
      parseInt(config.signBatchSize || "0", 10),
      0,
      128
    );
    var hintedBatchSize = parseInt(initiated.sign_batch_size_hint, 10);
    // Prefer server policy hints when present; use DOM override only if the
    // server did not provide a positive batch hint.
    var batchSize = Number.isFinite(hintedBatchSize) && hintedBatchSize > 0
      ? clampPositiveInt(hintedBatchSize, 32, 128)
      : configuredBatchSize > 0
        ? clampPositiveInt(configuredBatchSize, 32, 128)
        : clampPositiveInt(
          Math.max(64, maxConcurrency * 4),
          32,
          128
        );
    var totalParts = Math.ceil(file.size / partSize);
    var completeParts = [];
    var uploadedBytes = 0;
    var storageKey = multipartStateStorageKey(config, file);
    persistMultipartState(storageKey, {
      bucket: initiated.bucket,
      key: key,
      session_id:
        typeof initiated.session_id === "string"
          ? initiated.session_id
          : null,
      upload_id: uploadId,
      part_size_bytes: partSize,
      resumable_until:
        typeof initiated.resumable_until === "string"
          ? initiated.resumable_until
          : null,
      checksum_algorithm:
        typeof initiated.checksum_algorithm === "string"
          ? initiated.checksum_algorithm
          : null,
      checksum_mode:
        typeof initiated.checksum_mode === "string"
          ? initiated.checksum_mode
          : "none",
      completed_checksums_sha256: {},
    });

    async function uploadSinglePart(partNumber, url, checksumValue) {
      var start = (partNumber - 1) * partSize;
      var end = Math.min(file.size, start + partSize);
      var blob = file.slice(start, end);
      var attempt = 0;
      while (attempt < 3) {
        attempt += 1;
        try {
          var extraHeaders = checksumValue
            ? { "x-amz-checksum-sha256": checksumValue }
            : null;
          var etag = await putPart(url, blob, extraHeaders);
          uploadedBytes += blob.size;
          var pct = Math.floor((uploadedBytes / file.size) * 100);
          setProgress(config.progressStoreId, pct, "Uploading… " + pct + "%");
          return {
            part_number: partNumber,
            etag: etag,
            checksum_sha256: checksumValue || null,
          };
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
        var storedChecksums =
          storedMultipartState &&
          storedMultipartState.completed_checksums_sha256 &&
          typeof storedMultipartState.completed_checksums_sha256 === "object"
            ? storedMultipartState.completed_checksums_sha256
            : {};
        completedByPartNumber[partNumber] = {
          part_number: partNumber,
          etag: part.etag || "",
          checksum_sha256:
            typeof storedChecksums[String(partNumber)] === "string"
              ? storedChecksums[String(partNumber)]
              : null,
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
        var checksumsSha256 = null;
        if (
          initiated.checksum_algorithm === "SHA256" &&
          initiated.checksum_mode !== "none"
        ) {
          var checksumResults = await Promise.all(
            partNumbers.map(function (checksumPartNumber) {
              var checksumStart = (checksumPartNumber - 1) * partSize;
              var checksumEnd = Math.min(file.size, checksumStart + partSize);
              return sha256Base64FromBlob(file.slice(checksumStart, checksumEnd)).then(
                function (digest) {
                  return { partNumber: checksumPartNumber, digest: digest };
                }
              );
            })
          );
          checksumsSha256 = {};
          for (var checksumIndex = 0; checksumIndex < checksumResults.length; checksumIndex += 1) {
            var checksumResult = checksumResults[checksumIndex];
            checksumsSha256[String(checksumResult.partNumber)] = checksumResult.digest;
          }
        }

        var sign = await postJson(
          base + "/uploads/sign-parts",
          {
            key: key,
            upload_id: uploadId,
            part_numbers: partNumbers,
            checksums_sha256: checksumsSha256,
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
                var checksumValue =
                  checksumsSha256 && typeof checksumsSha256[String(partNumber)] === "string"
                    ? checksumsSha256[String(partNumber)]
                    : null;
                var completed = await uploadSinglePart(
                  partNumber,
                  signedUrl,
                  checksumValue
                );
                completedByPartNumber[partNumber] = completed;
                var persistedState = loadMultipartState(storageKey) || {};
                var persistedChecksums =
                  persistedState.completed_checksums_sha256 &&
                  typeof persistedState.completed_checksums_sha256 === "object"
                    ? persistedState.completed_checksums_sha256
                    : {};
                if (completed.checksum_sha256) {
                  persistedChecksums[String(partNumber)] = completed.checksum_sha256;
                  persistedState.completed_checksums_sha256 = persistedChecksums;
                  persistMultipartState(storageKey, persistedState);
                }
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

  function shouldUseAsyncExports(config, fileSize) {
    return (
      config.asyncExportsEnabled &&
      Number.isFinite(config.asyncExportMinBytes) &&
      fileSize >= config.asyncExportMinBytes
    );
  }

  async function createAsyncExport(config, uploadResult) {
    var exportsBase = config.exportsEndpointBase.replace(/\/$/, "");
    var idempotencyKey =
      "export-create:" + uploadResult.bucket + ":" + uploadResult.key;
    var createPayload = {
      source_key: uploadResult.key,
      filename: uploadResult.filename,
    };
    return postJson(
      exportsBase,
      createPayload,
      authorizedHeaders(config, { "Idempotency-Key": idempotencyKey })
    );
  }

  async function pollAsyncExport(config, exportId) {
    var startedMs = Date.now();
    var exportsBase = config.exportsEndpointBase.replace(/\/$/, "");
    while (true) {
      var exportResource = await getJson(
        exportsBase + "/" + encodeURIComponent(exportId),
        authorizedHeaders(config)
      );
      var status = exportResource.status || "";
      if (
        status === "succeeded" ||
        status === "failed" ||
        status === "cancelled"
      ) {
        return exportResource;
      }
      if (Date.now() - startedMs > config.asyncExportTimeoutMs) {
        throw new Error(
          "export status polling timed out after " +
            config.asyncExportTimeoutMs +
            "ms"
        );
      }
      await sleep(config.asyncExportPollIntervalMs);
    }
  }

  async function maybePresignExportDownload(config, exportResource) {
    var output =
      exportResource && typeof exportResource.output === "object"
        ? exportResource.output
        : null;
    if (!output) return null;
    if (typeof output.key !== "string" || !output.key) {
      return null;
    }
    var requestPayload = {
      key: output.key,
    };
    if (
      typeof output.download_filename === "string" &&
      output.download_filename
    ) {
      requestPayload.filename = output.download_filename;
    }
    var response = await postJson(
      config.transfersEndpointBase + "/downloads/presign",
      requestPayload,
      authorizedHeaders(config)
    );
    if (response && typeof response.url === "string" && response.url) {
      return {
        key: output.key,
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
    if (isResumableStateExpired(storedMultipartState)) {
      clearMultipartState(storageKey);
      storedMultipartState = null;
    }
    setProgress(config.progressStoreId, 0, "Preparing upload…");

    var initiated = null;
    var transferCapabilities = null;
    var checksumValue = null;
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
        session_id: storedMultipartState.session_id || null,
        resumable_until: storedMultipartState.resumable_until || null,
        checksum_algorithm: storedMultipartState.checksum_algorithm || null,
        checksum_mode: storedMultipartState.checksum_mode || "none",
        expires_in_seconds: 0,
      };
      setProgress(config.progressStoreId, 0, "Resuming upload…");
    } else {
      transferCapabilities = await fetchTransferCapabilities(config);
      var shouldUseSingleChecksum =
        transferCapabilities &&
        file.size < transferCapabilities.multipart_threshold_bytes &&
        shouldApplyChecksum(config, transferCapabilities);
      if (shouldUseSingleChecksum) {
        checksumValue = await sha256Base64FromBlob(file);
      }
      initiated = await postJson(
        config.transfersEndpointBase + "/uploads/initiate",
        buildInitiatePayload(config, file, contentType, {
          checksumValue: checksumValue,
        }),
        authorizedHeaders(config)
      );
    }

    var uploadResult = null;
    if (initiated.strategy === "single") {
      var singleUploadHeaders =
        initiated.checksum_algorithm === "SHA256" &&
        transferCapabilities &&
        shouldApplyChecksum(config, transferCapabilities) &&
        typeof checksumValue === "string" &&
        checksumValue
          ? { "x-amz-checksum-sha256": checksumValue }
          : null;
      await putObject(initiated.url, file, contentType, singleUploadHeaders);
      clearMultipartState(storageKey);
      uploadResult = buildUploadResult(
        file,
        initiated,
        contentType
      );
    } else if (initiated.strategy === "multipart") {
      try {
        await uploadMultipart(config, file, initiated, storedMultipartState);
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
          storedMultipartState = null;
          storageKey = multipartStateStorageKey(config, file);
          initiated = await postJson(
            config.transfersEndpointBase + "/uploads/initiate",
            buildInitiatePayload(config, file, contentType, null),
            authorizedHeaders(config)
          );
          if (initiated.strategy === "single") {
            await putObject(initiated.url, file, contentType, null);
            clearMultipartState(storageKey);
          } else if (initiated.strategy === "multipart") {
            await uploadMultipart(config, file, initiated, storedMultipartState);
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

    if (!shouldUseAsyncExports(config, file.size)) {
      return uploadResult;
    }

    setProgress(
      config.progressStoreId,
      100,
      "Upload complete. Creating export…"
    );
    var createdExport = await createAsyncExport(config, uploadResult);
    if (
      !createdExport ||
      typeof createdExport.export_id !== "string" ||
      !createdExport.export_id
    ) {
      throw new Error("export create response did not include an export_id");
    }

    setProgress(
      config.progressStoreId,
      100,
      "Processing in background. Waiting for export result…"
    );
    var exportResource = await pollAsyncExport(
      config,
      createdExport.export_id
    );
    if (
      exportResource.status === "failed" ||
      exportResource.status === "cancelled"
    ) {
      var errorMessage =
        typeof exportResource.error === "string" && exportResource.error
          ? exportResource.error
          : "background processing " + exportResource.status;
      throw new Error(errorMessage);
    }

    var download = await maybePresignExportDownload(config, exportResource);
    setProgress(config.progressStoreId, 100, "Processing complete");
    return {
      ...uploadResult,
      export_id: createdExport.export_id,
      export_status: exportResource.status,
      export_output: exportResource.output || null,
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
      exportsEndpointBase: root.dataset.exportsEndpointBase || "/v1/exports",
      authHeaderElementId: root.dataset.authHeaderElementId || "",
      maxConcurrency: root.dataset.maxConcurrency || "4",
      signBatchSize: root.dataset.signBatchSize || "",
      workloadClass: root.dataset.workloadClass || "",
      policyHint: root.dataset.policyHint || "",
      checksumPreference: root.dataset.checksumPreference || "",
      resumeNamespace: root.dataset.resumeNamespace || "",
      maxBytes: parseInt(root.dataset.maxBytes || "0", 10),
      resultStoreId: root.dataset.resultStoreId || "",
      progressStoreId: root.dataset.progressStoreId || "",
      asyncExportsEnabled: root.dataset.asyncExportsEnabled === "true",
      asyncExportMinBytes: parseInt(root.dataset.asyncExportMinBytes || "0", 10),
      asyncExportPollIntervalMs: Math.max(
        100,
        parseInt(root.dataset.asyncExportPollIntervalMs || "2000", 10) || 2000
      ),
      asyncExportTimeoutMs: Math.max(
        1000,
        parseInt(root.dataset.asyncExportTimeoutMs || "900000", 10) || 900000
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
