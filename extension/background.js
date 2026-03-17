// for manifest V3
// async function sendToLocalhost(url, html) {
//   const body = JSON.stringify({ url, body: html });
//   await fetch("http://127.0.0.1:5793/log-me", {
//     method: "POST",
//     headers: { "Content-Type": "application/json" },
//     body,
//   });
// }
//
// browser.commands.onCommand.addListener(async (command) => {
//   if (command !== "log-me") return;
//   const [tab] = await browser.tabs.query({ active: true, currentWindow: true });
//   if (!tab?.id) return;
//   const [{ result: html }] = await browser.scripting.executeScript({
//     target: { tabId: tab.id },
//     func: () => document.documentElement.outerHTML,
//   });
//   await sendToLocalhost(tab.url, html);
// });
//

function sendToLocalhost(url, html) {
  fetch("http://127.0.0.1:5793/log-me", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url, body: html })
  }).catch(console.error);
}

browser.commands.onCommand.addListener(async (command) => {
  if (command !== "log-me") return;
  const [tab] = await browser.tabs.query({ active: true, currentWindow: true });
  if (!tab?.id) return;
  browser.tabs.executeScript(tab.id, { code: "document.documentElement.outerHTML" })
    .then(([html]) => sendToLocalhost(tab.url, html))
    .catch(console.error);
});
