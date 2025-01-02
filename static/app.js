$(document).ready(function () {
    const ingestContent = $('#ingestContent');
    const fixedContent = $('#fixedContent');
    const analyzedText = $('#analyzedText');
    const timestamp = $('#timestamp');
    const counts = $('#counts');

    // Função para mostrar popup de decisão
    function showSourceConflictPopup(onSelect) {
        const popup = $(
            `<div id="sourceConflictPopup" style="position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%); background: white; padding: 20px; border: 1px solid #ccc; box-shadow: 0px 4px 6px rgba(0,0,0,0.1); z-index: 9999;">
                <h5>Conflito de fontes de texto</h5>
                <p>Detectamos que você carregou um arquivo e também inseriu texto manualmente. Por favor, escolha qual fonte deseja usar:</p>
                <button id="useFile" class="btn btn-primary">Usar Arquivo</button>
                <button id="useText" class="btn btn-secondary">Usar Texto Copiado</button>
            </div>`
        );

        $('body').append(popup);

        $('#useFile').on('click', function () {
            popup.remove();
            onSelect('file');
        });

        $('#useText').on('click', function () {
            popup.remove();
            onSelect('text');
        });
    }

    // Enviar conteúdo
    $('#ingestBtn').on('click', function () {
        const fileInput = $('#inputFile').val();
        const textInput = $('#inputText').val().trim();

        if (fileInput && textInput) {
            showSourceConflictPopup((selectedSource) => {
                const formData = new FormData($('#ingestForm')[0]);

                if (selectedSource === 'text') {
                    formData.delete('file');
                } else {
                    formData.set('text', ''); // Limpa o texto manual
                }

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
        } else {
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
        }
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
