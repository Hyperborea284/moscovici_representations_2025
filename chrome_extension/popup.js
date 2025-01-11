document.getElementById("extract").addEventListener("click", () => {
  chrome.tabs.query({ active: true, currentWindow: true }, tabs => {
    chrome.scripting.executeScript({
      target: { tabId: tabs[0].id },
      func: function () {
        // Captura o DOM da aba ativa
        const fullDOM = document.documentElement.outerHTML;
        console.log("Popup Script: DOM captured, length:", fullDOM.length);

        // Envia o DOM ao background
        chrome.runtime.sendMessage({
          action: "sendToAPI",
          data: fullDOM,
          url: window.location.href
        });
      }
    });
  });
});
