// /static/js/app.js

function loadTimelineList() {
    $.ajax({
        url: '/list_timelines',
        type: 'GET',
        success: function (data) {
            const timelineDropdown = $('#timelineDropdown');
            timelineDropdown.empty();
            if (data.status === "success" && data.timelines && data.timelines.length > 0) {
                data.timelines.forEach(timeline => {
                    timelineDropdown.append(`<option value="${timeline}">${timeline}</option>`);
                });
            } else {
                timelineDropdown.append('<option value="">Nenhuma timeline disponível</option>');
            }
        },
        error: function () {
            alert("Erro ao carregar a lista de timelines. Verifique o servidor.");
        }
    });
}

$(document).ready(function () {
    const ingestContent = $('#ingestContent');
    const fixedContent = $('#fixedContent');
    const analyzedText = $('#analyzedText');
    const timestamp = $('#timestamp');
    const counts = $('#counts');
    const linksErrorList = $('#linksErrorList');

    // Seleção de DB
    const dbSelectDropdown = $('#dbSelectDropdown');
    const loadDbBtn = $('#loadDbBtn');
    const saveDbBtn = $('#saveDbBtn');
    const deleteDbBtn = $('#deleteDbBtn');
    const dbLoadMessage = $('#dbLoadMessage');

    // LlamaIndex
    const llamaQueryInput = $('#llamaQueryInput');
    const sendLlamaBtn = $('#sendLlamaBtn');
    const llamaResponses = $('#llamaResponses');

    // Função para obter a lista de DBs
    function refreshDbList() {
        $.ajax({
            url: '/select_db',
            type: 'GET',
            dataType: 'json',
            success: function (response) {
                const dbFilesList = response.db_files || [];
                populateDbDropdown(dbFilesList);
            },
            error: function () {
                console.error("Erro ao obter lista de DBs em /select_db");
            }
        });
    }

    function populateDbDropdown(dbList) {
        dbSelectDropdown.empty();
        if (dbList.length > 0) {
            dbList.forEach(dbFile => {
                dbSelectDropdown.append(`<option value="${dbFile}">${dbFile}</option>`);
            });
        } else {
            dbSelectDropdown.append('<option value="">Nenhum DB disponível</option>');
        }
    }

    // Carregamos a lista de DBs ao iniciar
    refreshDbList();

    // Botão "Carregar DB Selecionado"
    loadDbBtn.on('click', function () {
        const selectedDb = dbSelectDropdown.val();
        if (!selectedDb) {
            alert("Nenhum DB selecionado.");
            return;
        }
        $.ajax({
            url: '/select_db',
            type: 'POST',
            data: { db_name: selectedDb },
            success: function (data) {
                if (data.status === "success") {
                    dbLoadMessage.text(`DB "${selectedDb}" carregado com sucesso!`)
                                 .show().fadeOut(3000);
                }
            },
            error: function (xhr) {
                const resp = xhr.responseJSON || {};
                alert(resp.error || "Erro ao carregar DB.");
            }
        });
    });

    // Botão "Salvar no DB"
    saveDbBtn.on('click', function() {
        $.ajax({
            url: '/save_to_db',
            type: 'POST',
            success: function (data) {
                if (data.status === "success") {
                    alert("Dados salvos com sucesso!");
                } else {
                    alert("Não foi possível salvar no DB: " + (data.message || data.error));
                }
            },
            error: function (xhr) {
                const resp = xhr.responseJSON || {};
                alert(resp.error || "Erro ao salvar no DB.");
            }
        });
    });

    // Botão "Excluir DB Selecionado"
    deleteDbBtn.on('click', function() {
        const selectedDb = dbSelectDropdown.val();
        if (!selectedDb) {
            alert("Nenhum DB selecionado para excluir.");
            return;
        }
        if (!confirm(`Deseja excluir o DB "${selectedDb}"? Esta ação é irreversível.`)) {
            return;
        }
        $.ajax({
            url: '/delete_db',
            type: 'POST',
            data: { db_name: selectedDb },
            success: function (data) {
                if (data.status === "success") {
                    alert(`DB "${selectedDb}" foi excluído.`);
                    refreshDbList();
                } else {
                    alert("Erro ao excluir DB: " + (data.error || data.message));
                }
            },
            error: function () {
                alert("Erro ao excluir DB. Verifique o servidor.");
            }
        });
    });

    // Perguntas via LlamaIndex (exemplo)
    sendLlamaBtn.on('click', function() {
        const question = llamaQueryInput.val().trim();
        if (!question) {
            alert("Digite uma pergunta.");
            return;
        }
        // Rota hipotética /llama_query
        $.ajax({
            url: '/llama_query',
            type: 'POST',
            data: JSON.stringify({ question: question }),
            contentType: 'application/json; charset=utf-8',
            dataType: 'json',
            success: function(data) {
                appendLlamaMessage(question, data.answer);
            },
            error: function() {
                alert("Erro ao consultar LlamaIndex. Verifique o servidor.");
            }
        });
    });

    function appendLlamaMessage(question, answer) {
        const now = new Date().toLocaleTimeString();
        llamaResponses.append(`
            <div><strong>Pergunta [${now}]:</strong> ${question}</div>
            <div style="margin-left:20px;"><strong>Resposta:</strong> ${answer}</div>
        `).scrollTop(llamaResponses[0].scrollHeight);
    }

    // Timeline: ao mudar o dropdown
    $('#timelineDropdown').on('change', function () {
        const filename = $(this).val();
        if (filename) {
            loadTimeline(filename);
        }
    });

    function loadTimeline(filename) {
        $.ajax({
            url: `/view_timeline?file=${filename}`,
            type: 'GET',
            dataType: 'json',
            success: function (data) {
                if (data.status === "success") {
                    $('#timelineResults').html(data.html);
                    fetchTimelineData(filename);
                } else {
                    alert("Erro ao carregar timeline: " + (data.message || data.error));
                }
            },
            error: function () {
                alert("Erro ao carregar timeline. Verifique o servidor.");
            }
        });
    }

    function fetchTimelineData(filename) {
        $.ajax({
            url: `/timeline_data?file=${filename}`,
            type: 'GET',
            dataType: 'json',
            success: function (data) {
                if (data) {
                    drawTimeline(data);
                } else {
                    alert("Erro ao carregar dados da timeline.");
                }
            },
            error: function () {
                alert("Erro ao buscar dados da timeline.");
            }
        });
    }

    // Conflito de fontes
    function showSourceConflictPopup(options, onSelect) {
        let message = '<p>Você preencheu mais de uma fonte de texto:</p><ul>';
        options.forEach(opt => {
            if (opt === 'file') message += '<li>Arquivo</li>';
            if (opt === 'text') message += '<li>Texto Copiado</li>';
            if (opt === 'links') message += '<li>Links</li>';
        });
        message += '</ul><p>Escolha qual fonte deseja usar:</p>';

        const popup = $(`
            <div id="sourceConflictPopup" style="position: fixed; top: 50%; left: 50%;
                 transform: translate(-50%, -50%); background: white; padding: 20px;
                 border: 1px solid #ccc; box-shadow: 0px 4px 6px rgba(0,0,0,0.1);
                 z-index: 9999;">
                <h5>Conflito de fontes de texto</h5>
                ${message}
            </div>
        `);

        options.forEach(opt => {
            let label = '';
            if (opt === 'file') label = 'Usar Arquivo';
            if (opt === 'text') label = 'Usar Texto Copiado';
            if (opt === 'links') label = 'Usar Links';
            const btn = $(`<button class="btn btn-primary m-1">${label}</button>`);
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
                    analyzedText.html(data.html_fixed.analyzedText || "Erro ao carregar texto.");
                    timestamp.html(data.html_fixed.timestamp || "");
                    counts.html(data.html_fixed.counts || "");
                    $('#sentimentResults').html(data.html_dynamic);
                    fixedContent.removeClass('d-none');
                } else {
                    alert("Erro ao processar resultados.");
                }
            },
            error: function () {
                alert("Erro ao processar análise de sentimentos.");
            }
        });
    }

    // Botão "Enviar Conteúdo"
    $('#ingestBtn').on('click', function () {
        linksErrorList.empty().hide();

        const fileInput = $('#inputFile').val();
        const textInput = $('#inputText').val().trim();
        const linksInput = $('#linksArea').val().trim();

        let sourcesUsed = [];
        if (fileInput) sourcesUsed.push('file');
        if (textInput) sourcesUsed.push('text');
        if (linksInput) sourcesUsed.push('links');

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
                            alert("Erro ao enviar conteúdo (arquivo).");
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
                            alert("Erro ao enviar conteúdo (texto).");
                        }
                    });
                } else if (selectedSource === 'links') {
                    let formData = new FormData();
                    formData.append('links', linksInput);
                    const loadingMsg = $('<p class="text-primary">Processando links...</p>');
                    ingestContent.append(loadingMsg);

                    $.ajax({
                        url: '/ingest_links',
                        type: 'POST',
                        data: formData,
                        processData: false,
                        contentType: false,
                        success: function (data) {
                            loadingMsg.remove();
                            ingestContent.addClass('d-none');
                            if (data.html_fixed) {
                                analyzedText.html(data.html_fixed.analyzedText || "Erro texto analisado.");
                                timestamp.html(data.html_fixed.timestamp || "");
                                counts.html(data.html_fixed.counts || "");
                            }
                            if (data.bad_links && data.bad_links.length > 0) {
                                linksErrorList.html(
                                    "<strong>Links com falha:</strong><br>" +
                                    data.bad_links.join("<br>")
                                ).show();
                            }
                            fixedContent.removeClass('d-none');
                        },
                        error: function () {
                            loadingMsg.remove();
                            alert("Erro ao enviar conteúdo (links).");
                        }
                    });
                }
            });
        } else {
            // Sem conflito
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
                        alert("Erro ao enviar conteúdo (arquivo).");
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
                        alert("Erro ao enviar conteúdo (texto).");
                    }
                });
            } else if (linksInput) {
                let formData = new FormData();
                formData.append('links', linksInput);
                const loadingMsg = $('<p class="text-primary">Processando links...</p>');
                ingestContent.append(loadingMsg);

                $.ajax({
                    url: '/ingest_links',
                    type: 'POST',
                    data: formData,
                    processData: false,
                    contentType: false,
                    success: function (data) {
                        loadingMsg.remove();
                        ingestContent.addClass('d-none');
                        if (data.html_fixed) {
                            analyzedText.html(data.html_fixed.analyzedText || "Erro texto analisado.");
                            timestamp.html(data.html_fixed.timestamp || "");
                            counts.html(data.html_fixed.counts || "");
                        }
                        if (data.bad_links && data.bad_links.length > 0) {
                            linksErrorList.html(
                                "<strong>Links com falha:</strong><br>" +
                                data.bad_links.join("<br>")
                            ).show();
                        }
                        fixedContent.removeClass('d-none');
                    },
                    error: function () {
                        loadingMsg.remove();
                        alert("Erro ao enviar conteúdo (links).");
                    }
                });
            } else {
                alert("Nenhuma fonte de conteúdo fornecida.");
            }
        }
    });

    // Botão Reset
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

    // Botão de Representação Social
    $('#contentBtn').on('click', function () {
        const formData = new FormData($('#contentForm')[0]);
        $.ajax({
            url: '/process',
            type: 'POST',
            data: formData,
            processData: false,
            contentType: false,
            success: function (resp) {
                if (typeof resp === 'object' && resp.html) {
                    $('#contentResults').html(resp.html);
                    $('#contentResults table').each(function () {
                        const colCount = $(this).find('thead th').length;
                        if (colCount > 0) {
                            $(this).DataTable({
                                paging: false,
                                info: false,
                                searching: false
                            });
                        }
                    });
                } else {
                    alert("Retorno inesperado da representação social.");
                }
            },
            error: function () {
                alert("Erro ao processar representação social.");
            }
        });
    });

    // Botão de Sentimentos
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
                        $('#sentimentResults').html(data.html_dynamic || "");
                    },
                    error: function () {
                        alert("Erro ao processar análise de sentimentos.");
                    }
                });
            },
            error: function () {
                alert("Erro ao selecionar algoritmo.");
            }
        });
    });

    // Botão de Timeline
    $('#timelineBtn').on('click', function () {
        const textInput = $('#inputText').val().trim();
        $.ajax({
            url: '/generate_timeline',
            type: 'POST',
            data: { text: textInput },
            success: function (data) {
                if (data.status === "success" || data.status === "cached") {
                    loadTimeline(data.timeline_file);
                    loadTimelineList();
                } else {
                    alert("Falha na geração da timeline: " + (data.error || data.message));
                }
            },
            error: function () {
                alert("Erro ao gerar timeline.");
            }
        });
    });

    // Botão de Identificar Entidades
    $('#identifyEntitiesBtn').on('click', function () {
        $.ajax({
            url: '/identify_entities',
            type: 'POST',
            success: function (data) {
                if (data.status === "success") {
                    $('#entitiesResults').html(renderEntities(data.entities));
                    if (data.entities.map_html) {
                        $('#mapContainer').html(data.entities.map_html);
                    }
                } else if (data.status === "cached") {
                    if (typeof data.entities === "string") {
                        try {
                            let obj = JSON.parse(data.entities);
                            $('#entitiesResults').html(renderEntities(obj));
                            if (obj.map_html) {
                                $('#mapContainer').html(obj.map_html);
                            }
                        } catch (e) {
                            $('#entitiesResults').html(`<pre>${data.entities}</pre>`);
                        }
                    } else {
                        $('#entitiesResults').html(renderEntities(data.entities));
                        if (data.entities.map_html) {
                            $('#mapContainer').html(data.entities.map_html);
                        }
                    }
                } else {
                    alert("Erro ao identificar entidades.");
                }
            },
            error: function () {
                alert("Erro ao identificar entidades.");
            }
        });
    });

    function renderEntities(entities) {
        let html = '<div class="coluna">';
        if (entities.topicos && entities.topicos.length > 0) {
            html += '<h2>Tópicos Principais:</h2><ul>';
            entities.topicos.forEach(top => {
                html += `<li>${top}</li>`;
            });
            html += '</ul>';
        }
        if (entities.resumo) {
            html += `<h2>Resumo:</h2><p>${entities.resumo}</p>`;
        }
        if (entities.pessoas && entities.pessoas.length > 0) {
            html += '<h2>Pessoas e Organizações:</h2><ul>';
            entities.pessoas.forEach(pessoa => {
                html += `
                    <li class="entidade">
                        <strong>${pessoa.entidade}</strong>
                        <span class="emoji">
                            ${pessoa.sentimento > 0.05 ? '😊' : pessoa.sentimento < -0.05 ? '😠' : '😐'}
                        </span>
                        ${pessoa.imagem ? `<img src="${pessoa.imagem}" alt="${pessoa.entidade}" class="imagem-miniatura">` : ''}
                    </li>
                `;
            });
            html += '</ul>';
        }
        if (entities.localizacoes && entities.localizacoes.length > 0) {
            html += '<h2>Localizações:</h2><ul>';
            entities.localizacoes.forEach(loc => {
                html += `
                    <li class="entidade">
                        <strong>${loc.entidade}</strong>
                        <span class="emoji">
                            ${loc.sentimento > 0.05 ? '😊' : loc.sentimento < -0.05 ? '😠' : '😐'}
                        </span>
                        ${loc.imagem ? `<img src="${loc.imagem}" alt="${loc.entidade}" class="imagem-miniatura">` : ''}
                    </li>
                `;
            });
            html += '</ul>';
        }
        html += '</div>';
        return html;
    }

    // Botão de Gerar Cenários
    $('#generateCenariosBtn').on('click', function () {
        $.ajax({
            url: '/generate_cenarios',
            type: 'POST',
            success: function (data) {
                if (data.html) {
                    $('#cenariosResults').html(data.html);
                } else {
                    alert("Não foi possível gerar cenários.");
                }
            },
            error: function () {
                alert("Erro ao gerar cenários.");
            }
        });
    });
});
