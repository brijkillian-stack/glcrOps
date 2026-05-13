  async function handleFileUpload(file: File) {
    if (!file.name.match(/\.(xlsx|xls)$/i)) {
      setUploadResult({ ok: false, message: "Only .xlsx or .xls files are supported." });
      setTimeout(() => setUploadResult(null), 4000);
      return;
    }
    setUploading(true);
    setUploadResult(null);
    try {
      const result = await uploadScheduleForWeek("", file);
      const msg = result.week_ending ? `Linked to week ending ${result.week_ending}` : result.message ?? "Uploaded successfully";
      setUploadResult({ ok: true, message: msg });
      reloadWeeks();
      setTimeout(() => setUploadResult(null), 5000);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Upload failed";
      setUploadResult({ ok: false, message: msg });
      setTimeout(() => setUploadResult(null), 5000);
    } finally {
      setUploading(false);
    }
  }