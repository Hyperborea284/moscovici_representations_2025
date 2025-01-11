function sendFullDOM() {
    // Captura o DOM inteiro da página
    const fullDOM = document.documentElement.outerHTML;

    console.log("Content Script: DOM captured, length:", fullDOM.length);

    // Envia o conteúdo do DOM para o background script
    chrome.runtime.sendMessage({
        action: "sendToAPI",
        data: fullDOM,
        url: window.location.href // Inclui o URL atual para referência
    }, (response) => {
        if (chrome.runtime.lastError) {
            console.error("Content Script: Error sending message:", chrome.runtime.lastError);
        } else {
            console.log("Content Script: Message sent, response:", response);
        }
    });
}

// Escuta o carregamento completo da página
window.addEventListener("load", () => {
    console.log("Content Script: Page loaded on URL:", window.location.href);
    sendFullDOM();
});
