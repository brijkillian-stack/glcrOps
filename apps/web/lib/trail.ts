export async function logToTrail(action: string, details: string) {
  try {
    await fetch('/api/trail', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action, details }),
    });
  } catch (error) {
    console.error('Failed to log to Trail:', error);
  }
}