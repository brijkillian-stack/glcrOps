    try {
      const result = await uploadScheduleForWeek("", file);
      const msg = result.week_ending 
        ? `Linked to week ending ${result.week_ending}` 
        : "Uploaded successfully";
      setUploadResult({ ok: true, message: msg });
      reloadWeeks();
      setTimeout(() => setUploadResult(null), 5000);
    } catch (err) {