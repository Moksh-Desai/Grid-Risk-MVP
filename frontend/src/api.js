export async function assessSite(data) {
  const endpoints = [
    "/api/assess-site",
    "https://silver-enigma-p7gjqrx66pj7crpgw-8000.app.github.dev/api/assess-site",
  ];

  let lastError = null;

  for (const url of endpoints) {
    try {
      const response = await fetch(url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(data),
      });

      if (!response.ok) {
        const text = await response.text();
        lastError = new Error(`API error ${response.status}: ${text}`);
        continue;
      }

      const result = await response.json();
      return result;
    } catch (err) {
      lastError = err;
      continue;
    }
  }

  throw lastError || new Error("API request failed");
}