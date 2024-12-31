$(document).ready(function () {
    const ingestContent = $('#ingestContent');
    const fixedContent = $('#fixedContent');
    const analyzedText = $('#analyzedText');
    const timestamp = $('#timestamp');
    const counts = $('#counts');

    // Enviar conteúdo
    $('#ingestBtn').on('click', function () {
        const formData = new FormData($('#ingestForm')[0]);
        $.ajax({
            url: '/ingest_content',
            type: 'POST',
            data: formData,
            processData: false,
            contentType: false,
            success: function () {
                ingestContent.addClass('d-none');
                fixedContent.removeClass('d-none');
                $.ajax({
                    url: '/process_sentiment',
                    type: 'POST',
                    success: function (data) {
                        if (data.html_fixed && data.html_dynamic) {
                            analyzedText.html(data.html_fixed.analyzedText || "Erro ao carregar texto analisado.");
                            timestamp.html(data.html_fixed.timestamp || "Erro ao carregar timestamp.");
                            counts.html(data.html_fixed.counts || "Erro ao carregar contagem.");
                            $('#sentimentResults').html(data.html_dynamic);
                        } else {
                            alert("Erro ao processar os resultados. Verifique o servidor.");
                        }
                    },
                    error: function () {
                        alert("Erro ao processar a análise de sentimentos. Verifique o servidor.");
                    }
                });
            },
            error: function () {
                alert("Erro ao enviar conteúdo. Verifique o servidor.");
            }
        });
    });

    // Reiniciar análise
    $('#resetBtn').on('click', function () {
        $.post('/reset_content', function () {
            fixedContent.addClass('d-none');
            ingestContent.removeClass('d-none');
            $('#inputText').val('');
            $('#inputFile').val('');
        });
    });

    // Representação Social
    $('#contentBtn').on('click', function () {
        const formData = new FormData($('#contentForm')[0]);
        $.ajax({
            url: '/process',
            type: 'POST',
            data: formData,
            processData: false,
            contentType: false,
            success: function (data) {
                $('#contentResults').html(data.html);

                $('#contentResults table').each(function () {
                    const columnCount = $(this).find('thead th').length;
                    if (columnCount > 0) {
                        $(this).DataTable({
                            paging: false,
                            info: false,
                            searching: false,
                        });
                    }
                });
            },
            error: function () {
                alert("Erro ao processar representação social. Verifique o servidor.");
            }
        });
    });

    // Análise de Sentimentos
    $('#sentimentBtn').on('click', function () {
        const formData = new FormData($('#sentimentForm')[0]);
        $.ajax({
            url: '/select_algorithm_and_generate',
            type: 'POST',
            data: formData,
            processData: false,
            contentType: false,
            success: function () {
                $.ajax({
                    url: '/process_sentiment',
                    type: 'POST',
                    success: function (data) {
                        $('#sentimentResults').html(data.html_dynamic);
                    },
                    error: function () {
                        alert("Erro ao processar a análise de sentimentos. Verifique o servidor.");
                    }
                });
            },
            error: function () {
                alert("Erro ao selecionar o algoritmo. Verifique o servidor.");
            }
        });
    });
});
