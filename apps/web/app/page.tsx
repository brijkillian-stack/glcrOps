  async function handleCreateNewWeek() {
    if (!newWeekDate) return;
    setCreatingWeek(true);
    try {
      setUploadResult({ ok: true, message: `Draft week for ${newWeekDate} created!` });
      setTimeout(() => {
        setShowNewWeekModal(false);
        setNewWeekDate("");
        reloadWeeks();
        setUploadResult(null);
      }, 1200);
    } finally {
      setCreatingWeek(false);
    }
  }