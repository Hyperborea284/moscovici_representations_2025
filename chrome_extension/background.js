chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    console.log("Background Script: Received message:", request);

    if (request.action === "sendToAPI") {
        console.log("Background Script: Sending data to API, length:", request.data.length);

        fetch("http://127.0.0.1:5000/api/", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ dom: request.data, url: request.url })
        })
        .then(response => response.json())
        .then(data => {
            console.log("Background Script: Response from API:", data);
            sendResponse({ status: "success", apiResponse: data });
        })
        .catch(error => {
            console.error("Background Script: Error sending data to API:", error);
            sendResponse({ status: "error", error: error.toString() });
        });

        // Indica que a resposta será assíncrona
        return true;
    }
});
