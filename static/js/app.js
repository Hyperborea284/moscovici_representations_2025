$(document).ready(function () {
    const ingestContent = $('#ingestContent');
    const fixedContent = $('#fixedContent');
    const analyzedText = $('#analyzedText');
    const timestamp = $('#timestamp');
    const counts = $('#counts');
    const linksErrorList = $('#linksErrorList');

    // Função para carregar a lista de timelines disponíveis
    function loadTimelineList() {
        $.ajax({
            url: '/list_timelines', // Rota para listar os arquivos de timeline
            type: 'GET',
            success: function (data) {
                const timelineFiles = $('#timelineFiles');
                timelineFiles.empty(); // Limpa a lista atual
                if (data.timelines && data.timelines.length > 0) {
                    data.timelines.forEach(timeline => {
                        const listItem = $(`<li class="list-group-item">${timeline}</li>`);
                        listItem.on('click', function () {
                            loadTimeline(timeline); // Carrega a timeline selecionada
                        });
                        timelineFiles.append(listItem);
                    });
                } else {
                    timelineFiles.append('<li class="list-group-item">Nenhuma timeline disponível.</li>');
                }
            },
            error: function () {
                alert("Erro ao carregar a lista de timelines. Verifique o servidor.");
            }
        });
    }

    // Função para carregar uma timeline específica
    function loadTimeline(filename) {
        $.ajax({
            url: `/view_timeline?file=${filename}`,
            type: 'GET',
            dataType: 'json',
            success: function (data) {
                if (data.status === "success") {
                    $('#timelineResults').html(data.html); // Exibe a timeline
                    // Chama a função para carregar os dados da timeline
                    fetchTimelineData(filename);
                } else {
                    alert("Erro ao carregar a timeline: " + data.error);
                }
            },
            error: function () {
                alert("Erro ao carregar a timeline. Verifique o servidor.");
            }
        });
    }

    // Função para buscar os dados da timeline
    function fetchTimelineData(filename) {
        $.ajax({
            url: `/timeline_data?file=${filename}`,
            type: 'GET',
            dataType: 'json',
            success: function (data) {
                if (data) {
                    drawTimeline(data); // Desenha a timeline com os dados recebidos
                } else {
                    alert("Erro ao carregar os dados da timeline.");
                }
            },
            error: function (xhr, status, error) {
                console.error("Erro ao buscar os dados da timeline:", error);
                alert("Erro ao buscar os dados da timeline. Verifique o servidor.");
            }
        });
    }

    // Função para mostrar popup de decisão (adaptada para três fontes)
    function showSourceConflictPopup(options, onSelect) {
        let message = '<p>Detectamos que você preencheu mais de uma fonte de texto:</p><ul>';
        options.forEach(opt => {
            if (opt === 'file') message += '<li>Arquivo</li>';
            if (opt === 'text') message += '<li>Texto Copiado</li>';
            if (opt === 'links') message += '<li>Links</li>';
        });
        message += '</ul><p>Por favor, escolha qual fonte deseja usar:</p>';

        let popup = $(
            `<div id="sourceConflictPopup" style="position: fixed; top: 50%; left: 50%; 
                 transform: translate(-50%, -50%); background: white; padding: 20px; 
                 border: 1px solid #ccc; box-shadow: 0px 4px 6px rgba(0,0,0,0.1); 
                 z-index: 9999;">
                <h5>Conflito de fontes de texto</h5>
                ${message}
            </div>`
        );

        options.forEach(opt => {
            let label = '';
            if (opt === 'file') label = 'Usar Arquivo';
            if (opt === 'text') label = 'Usar Texto Copiado';
            if (opt === 'links') label = 'Usar Links';
            let btn = $(`<button class="btn btn-primary m-1">${label}</button>`);
            btn.on('click', function () {
                popup.remove();
                onSelect(opt);
            });
            popup.append(btn);
        });

        $('body').append(popup);
    }

    function processSentiment() {
        $.ajax({
            url: '/process_sentiment',
            type: 'POST',
            success: function (data) {
                if (data.html_fixed && data.html_dynamic) {
                    analyzedText.html(data.html_fixed.analyzedText || "Erro ao carregar texto analisado.");
                    timestamp.html(data.html_fixed.timestamp || "Erro ao carregar timestamp.");
                    counts.html(data.html_fixed.counts || "Erro ao carregar contagem.");
                    $('#sentimentResults').html(data.html_dynamic);
                    fixedContent.removeClass('d-none'); // Certificar que o conteúdo é exibido
                } else {
                    alert("Erro ao processar os resultados. Verifique o servidor.");
                }
            },
            error: function () {
                alert("Erro ao processar a análise de sentimentos. Verifique o servidor.");
            }
        });
    }

    // Botão de Enviar Conteúdo
    $('#ingestBtn').on('click', function () {
        linksErrorList.empty().hide();

        const fileInput = $('#inputFile').val();
        const textInput = $('#inputText').val().trim();
        const linksInput = $('#linksArea').val().trim();

        let sourcesUsed = [];
        if (fileInput) sourcesUsed.push('file');
        if (textInput) sourcesUsed.push('text');
        if (linksInput) sourcesUsed.push('links');

        // Verificar o formato do arquivo se selecionado
        if (fileInput && !fileInput.endsWith('.txt')) {
            alert('Apenas arquivos .txt são permitidos.');
            return;
        }

        if (sourcesUsed.length > 1) {
            showSourceConflictPopup(sourcesUsed, (selectedSource) => {
                if (selectedSource === 'file') {
                    let formData = new FormData($('#ingestForm')[0]);
                    formData.delete('text');
                    formData.delete('links');
                    $.ajax({
                        url: '/ingest_content',
                        type: 'POST',
                        data: formData,
                        processData: false,
                        contentType: false,
                        success: function () {
                            ingestContent.addClass('d-none');
                            processSentiment();
                        },
                        error: function () {
                            alert("Erro ao enviar conteúdo (arquivo). Verifique o servidor.");
                        }
                    });
                } else if (selectedSource === 'text') {
                    let formData = new FormData();
                    formData.append('text', textInput);
                    $.ajax({
                        url: '/ingest_content',
                        type: 'POST',
                        data: formData,
                        processData: false,
                        contentType: false,
                        success: function () {
                            ingestContent.addClass('d-none');
                            processSentiment();
                        },
                        error: function () {
                            alert("Erro ao enviar conteúdo (texto). Verifique o servidor.");
                        }
                    });
                } else if (selectedSource === 'links') {
                    let formData = new FormData();
                    formData.append('links', linksInput);

                    // Exibir mensagem de aguarde
                    const loadingMessage = $('<p class="text-primary">Aguarde enquanto processamos os links...</p>');
                    ingestContent.append(loadingMessage);

                    $.ajax({
                        url: '/ingest_links',
                        type: 'POST',
                        data: formData,
                        processData: false,
                        contentType: false,
                        success: function (data) {
                            loadingMessage.remove();
                            ingestContent.addClass('d-none');
                            if (data.html_fixed) {
                                analyzedText.html(data.html_fixed.analyzedText || "Erro ao carregar texto analisado.");
                                timestamp.html(data.html_fixed.timestamp || "Erro ao carregar timestamp.");
                                counts.html(data.html_fixed.counts || "Erro ao carregar contagem.");
                            }
                            if (data.bad_links && data.bad_links.length > 0) {
                                linksErrorList.html(
                                    "<strong>Links com falha ou sem conteúdo:</strong><br>" +
                                    data.bad_links.join("<br>")
                                ).show();
                            }
                            fixedContent.removeClass('d-none');
                        },
                        error: function () {
                            loadingMessage.remove();
                            alert("Erro ao enviar conteúdo (links). Verifique o servidor.");
                        }
                    });
                }
            });
        } else {
            if (fileInput) {
                let formData = new FormData($('#ingestForm')[0]);
                $.ajax({
                    url: '/ingest_content',
                    type: 'POST',
                    data: formData,
                    processData: false,
                    contentType: false,
                    success: function () {
                        ingestContent.addClass('d-none');
                        processSentiment();
                    },
                    error: function () {
                        alert("Erro ao enviar conteúdo (arquivo). Verifique o servidor.");
                    }
                });
            } else if (textInput) {
                let formData = new FormData();
                formData.append('text', textInput);
                $.ajax({
                    url: '/ingest_content',
                    type: 'POST',
                    data: formData,
                    processData: false,
                    contentType: false,
                    success: function () {
                        ingestContent.addClass('d-none');
                        processSentiment();
                    },
                    error: function () {
                        alert("Erro ao enviar conteúdo (texto). Verifique o servidor.");
                    }
                });
            } else if (linksInput) {
                let formData = new FormData();
                formData.append('links', linksInput);

                // Exibir mensagem de aguarde
                const loadingMessage = $('<p class="text-primary">Aguarde enquanto processamos os links...</p>');
                ingestContent.append(loadingMessage);

                $.ajax({
                    url: '/ingest_links',
                    type: 'POST',
                    data: formData,
                    processData: false,
                    contentType: false,
                    success: function (data) {
                        loadingMessage.remove();
                        ingestContent.addClass('d-none');
                        if (data.html_fixed) {
                            analyzedText.html(data.html_fixed.analyzedText || "Erro ao carregar texto analisado.");
                            timestamp.html(data.html_fixed.timestamp || "Erro ao carregar timestamp.");
                            counts.html(data.html_fixed.counts || "Erro ao carregar contagem.");
                        }
                        if (data.bad_links && data.bad_links.length > 0) {
                            linksErrorList.html(
                                "<strong>Links com falha ou sem conteúdo:</strong><br>" +
                                data.bad_links.join("<br>")
                            ).show();
                        }
                        fixedContent.removeClass('d-none');
                    },
                    error: function () {
                        loadingMessage.remove();
                        alert("Erro ao enviar conteúdo (links). Verifique o servidor.");
                    }
                });
            } else {
                alert("Nenhuma fonte de conteúdo fornecida.");
            }
        }
    });

    // Botão de Reset
    $('#resetBtn').on('click', function () {
        $.post('/reset_content', function () {
            fixedContent.addClass('d-none');
            ingestContent.removeClass('d-none');
            $('#inputText').val('');
            $('#inputFile').val('');
            $('#linksArea').val('');
            linksErrorList.empty().hide();
        });
    });

    // Botão de Análise de Representação Social
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

    // Botão de Análise de Sentimentos
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

    // Botão de Geração de Timeline
    $('#timelineBtn').on('click', function () {
        const textInput = $('#inputText').val().trim();

        $.ajax({
            url: '/generate_timeline',
            type: 'POST',
            data: { text: textInput },
            success: function (data) {
                if (data.status === "success") {
                    // Carrega a timeline gerada
                    loadTimeline(data.timeline_file);
                    // Atualiza a lista de timelines
                    loadTimelineList();
                } else {
                    alert("Falha na geração da timeline: " + data.error);
                }
            },
            error: function () {
                alert("Erro ao gerar timeline. Verifique o servidor.");
            }
        });
    });

    // Carregar entidades e localidades ao abrir a aba
    $('#entities-tab').on('click', function () {
        $.ajax({
            url: '/entities_and_locations',
            type: 'GET',
            success: function (data) {
                $('#entitiesResults').html(data);
            },
            error: function () {
                alert("Erro ao carregar entidades e localidades. Verifique o servidor.");
            }
        });
    });
});