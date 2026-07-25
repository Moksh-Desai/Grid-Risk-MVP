export async function assessSite(data) {
  const response = await fetch(
    "https://silver-enigma-p7gjqrx66pj7crpgw-8000.app.github.dev/api/assess-site",
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(data),
    }
  );

  const result = await response.json();

  return result;
}