// Exemplo de JavaScript para interações futuras
document.addEventListener("DOMContentLoaded", function () {
    console.log("Página carregada!");

    // Mostra a mensagem de processamento quando o formulário é enviado
    const form = document.querySelector("form");
    const processingDiv = document.getElementById("processing");

    if (form && processingDiv) {
        form.addEventListener("submit", function() {
            processingDiv.style.display = "block";
        });
    }
});
