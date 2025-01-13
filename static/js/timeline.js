document.addEventListener("DOMContentLoaded", function () {
    const timeline = document.getElementById("timelineContainer"); // Atualizado
    const categoryBox = document.getElementById("category-box");
    const eventDescription = document.getElementById("event-description");

    let svgWidth, svgHeight, svg, timeScale;

    // Faz o fetch dos dados JSON
    fetch("/timeline_data")
        .then(response => response.json())
        .then(data => {
            if (!data.view || !data.view.start || !data.view.end) {
                console.error("Dados 'view' inválidos ou ausentes no JSON da timeline.");
                return;
            }
            drawTimeline(data);
            setupCategoryBox(data.categories);
        })
        .catch(error => {
            console.error("Falha ao buscar os dados da timeline:", error);
        });

    /**
     * Função principal de desenho da timeline
     */
    function drawTimeline(data) {
        // Permite rolagem se exceder dimensões
        const container = d3.select("#timelineContainer") // Atualizado
            .style("overflow", "auto")
            .style("max-height", "600px");

        // Dimensões "grandes" para acomodar bastante espaço
        svgWidth = 2000;
        svgHeight = 800;

        const startDate = new Date(data.view.start);
        const endDate = new Date(data.view.end);

        // Escala de tempo dinâmica
        timeScale = d3.scaleTime()
            .domain([startDate, endDate])
            .range([0, svgWidth]);

        // Cria SVG
        svg = container.append("svg")
            .attr("width", svgWidth)
            .attr("height", svgHeight)
            .style("background", "#fff");

        // -----------------------------------------
        // Desenho das Eras (já existente no código)
        // -----------------------------------------
        data.eras.forEach(era => {
            const eraStart = timeScale(new Date(era.start));
            const eraEnd = timeScale(new Date(era.end));
            const rectWidth = Math.max(1, eraEnd - eraStart);

            // Fundo suave para a era
            svg.append("rect")
                .attr("x", eraStart)
                .attr("width", rectWidth)
                .attr("y", svgHeight / 2 - 50)
                .attr("height", 100)
                .attr("fill", "rgba(173, 216, 230, 0.3)") 
                .attr("class", "era");

            // Texto da era
            svg.append("text")
                .attr("x", eraStart + 10)
                .attr("y", (svgHeight / 2) - 55)
                .attr("fill", "#000")
                .style("font-size", "12px")
                .text(era.name);

            // Linhas de início/fim da era
            svg.append("line")
                .attr("x1", eraStart)
                .attr("x2", eraStart)
                .attr("y1", 0)
                .attr("y2", svgHeight)
                .style("stroke", "#222")
                .style("stroke-width", 3);

            svg.append("line")
                .attr("x1", eraEnd)
                .attr("x2", eraEnd)
                .attr("y1", 0)
                .attr("y2", svgHeight)
                .style("stroke", "#222")
                .style("stroke-width", 3);
        });

        // -----------------------------------------
        // Desenho dos Eventos (já existente)
        // -----------------------------------------
        const eventGroup = svg.append("g").attr("class", "events");
        const occupiedLevels = [];

        // Ordena eventos pela data de início (opcional, para controlar quem fica "em cima")
        const sortedEvents = data.events.slice().sort((a, b) => {
            const aStart = new Date(a.start).getTime();
            const bStart = new Date(b.start).getTime();
            return aStart - bStart;
        });

        sortedEvents.forEach(event => {
            const startX = timeScale(new Date(event.start));
            const endX = timeScale(new Date(event.end));
            const rawWidth = endX - startX;
            const eventWidth = Math.max(40, rawWidth);

            // Mede texto para dimensionar retângulo
            const tempText = eventGroup.append("text")
                .attr("x", -9999)
                .attr("y", -9999)
                .style("font-size", "12px")
                .text(event.text);
            const textBBox = tempText.node().getBBox();
            tempText.remove();

            const rectHeight = textBBox.height + 8;
            const neededWidth = textBBox.width + 10;
            const finalWidth = Math.max(eventWidth, neededWidth);

            // Empilhamento acima/abaixo da linha central
            let yOffset = svgHeight / 2;
            let level = 0;
            while (
                occupiedLevels[level] &&
                occupiedLevels[level].some(range => overlaps(range, {
                    startX: startX,
                    endX: startX + finalWidth,
                    top: yOffset,
                    bottom: yOffset + rectHeight
                }))
            ) {
                level++;
                const direction = level % 2 === 0 ? -1 : 1;
                const offset = 40 + (level * 25);
                yOffset = (svgHeight / 2) + (direction * offset);
            }
            if (!occupiedLevels[level]) occupiedLevels[level] = [];

            // Se sobrepõe, alarga o evento mais antigo
            occupiedLevels[level].forEach(existing => {
                if (overlaps(existing, {
                    startX: startX,
                    endX: startX + finalWidth,
                    top: yOffset,
                    bottom: yOffset + rectHeight
                })) {
                    existing.rectRef.attr("height", parseFloat(existing.rectRef.attr("height")) + 5);
                }
            });

            const eventRect = eventGroup.append("rect")
                .attr("x", startX)
                .attr("y", yOffset)
                .attr("width", finalWidth)
                .attr("height", rectHeight)
                .attr("fill", data.categories[event.category]?.color || "#ccc")
                .attr("stroke", "#555")
                .attr("stroke-width", 1)
                .attr("class", `event-${event.category}`)
                .on("mouseover", (e) => showDescription(event, e))
                .on("mouseout", hideDescription);

            eventGroup.append("text")
                .attr("x", startX + 5)
                .attr("y", yOffset + (rectHeight / 2) + (textBBox.height * 0.35))
                .attr("fill", "#000")
                .style("font-size", "12px")
                .text(event.text);

            occupiedLevels[level].push({
                startX,
                endX: startX + finalWidth,
                top: yOffset,
                bottom: yOffset + rectHeight,
                rectRef: eventRect
                // Removido 'overlaps' aqui, pois agora usamos a função global
            });
        });

        // -----------------------------------------
        // Linha central
        // -----------------------------------------
        svg.append("line")
            .attr("x1", 0)
            .attr("x2", svgWidth)
            .attr("y1", svgHeight / 2)
            .attr("y2", svgHeight / 2)
            .attr("stroke", "#000")
            .attr("stroke-width", 2);

        // Adiciona a linha de referência horizontal com datas/tempos dinâmicos
        addTimeAxis(svg, startDate, endDate);

        // Eixo superior semanal
        addWeekAxis(svg, startDate, endDate);
    }

    /**
     * Verifica sobreposição horizontal e vertical entre dois ranges.
     * @param {Object} range1 - Primeiro range com propriedades startX, endX, top, bottom.
     * @param {Object} range2 - Segundo range com propriedades startX, endX, top, bottom.
     * @returns {boolean} - Retorna true se houver sobreposição, false caso contrário.
     */
    function overlaps(range1, range2) {
        const hOverlap = range1.startX < range2.endX && range1.endX > range2.startX;
        const vOverlap = range1.top < range2.bottom && range1.bottom > range2.top;
        return hOverlap && vOverlap;
    }

    // Adiciona o eixo de tempo dinâmico
    function addTimeAxis(svg, startDate, endDate) {
        const stepMs = getDynamicStep(startDate, endDate);
        let current = new Date(startDate);

        while (current <= endDate) {
            const xPos = timeScale(current);

            // Desenha a linha vertical pontilhada para cada divisão
            svg.append("line")
                .attr("x1", xPos)
                .attr("x2", xPos)
                .attr("y1", 0)
                .attr("y2", svgHeight)
                .attr("stroke", "#ccc")
                .attr("stroke-dasharray", "2,2");

            // Formata o rótulo dependendo da escala
            const label = formatDynamicLabel(current, stepMs);

            // Se for sábado(6) ou domingo(0) e estamos em escala diária ou maior
            // => coloca em negrito
            let fontWeight = "normal";
            if (stepMs >= 86400000 && stepMs < 2592000000) {
                const dayIndex = current.getDay();
                if (dayIndex === 6 || dayIndex === 0) {
                    fontWeight = "bold";
                }
            }

            // Coloca o label próximo à linha central
            svg.append("text")
                .attr("x", xPos + 3)
                .attr("y", (svgHeight / 2) - 5)
                .attr("fill", "#000")
                .style("font-size", "10px")
                .style("font-weight", fontWeight)
                .text(label);

            // Incrementa data
            current = new Date(current.getTime() + stepMs);
        }
    }

    /**
     * Formata o rótulo dependendo do passo de tempo.
     */
    function formatDynamicLabel(date, stepMs) {
        const dayOfWeek = date.toLocaleString("pt-BR", { weekday: "short" }); // ex: seg., ter., qua...
        const dayNum = date.getDate();
        const monthShort = date.toLocaleString("pt-BR", { month: "short" });  // jan, fev, etc.
        const year = date.getFullYear();

        const hours = String(date.getHours()).padStart(2, "0");
        const minutes = String(date.getMinutes()).padStart(2, "0");
        const seconds = String(date.getSeconds()).padStart(2, "0");

        if (stepMs < 60 * 1000) {
            // < 1 min => HH:MM:SS
            return `${hours}:${minutes}:${seconds}`;
        } else if (stepMs < 60 * 60 * 1000) {
            // < 1 hora => HH:MM
            return `${hours}:${minutes}`;
        } else if (stepMs < 24 * 60 * 60 * 1000) {
            // < 1 dia => exibe "HH:MM, Dia Mês"
            return `${hours}:${minutes}  ${dayNum} ${monthShort}`;
        } else if (stepMs < 30 * 24 * 60 * 60 * 1000) {
            // < ~1 mês => seg. 6, ter. 7, ...
            return `${dayOfWeek} ${dayNum}`;
        } else if (stepMs < 365 * 24 * 60 * 60 * 1000) {
            // < 1 ano => 6 jan
            return `${dayNum} ${monthShort}`;
        }
        // >= 1 ano => só exibe o ano
        return `${year}`;
    }

    // Adiciona o eixo superior semanal
    function addWeekAxis(svg, startDate, endDate) {
        let current = new Date(startDate);
        let weekCount = 1;

        while (current < endDate) {
            const weekStart = new Date(current);
            const weekEnd = new Date(weekStart);
            weekEnd.setDate(weekEnd.getDate() + 6);

            if (weekEnd > endDate) {
                weekEnd.setTime(endDate.getTime());
            }

            const xStart = timeScale(weekStart);
            const xEnd = timeScale(weekEnd);

            svg.append("line")
                .attr("x1", xStart)
                .attr("x2", xStart)
                .attr("y1", 0)
                .attr("y2", svgHeight)
                .style("stroke", "#444")
                .style("stroke-width", 2);

            const startLabel = formatDateLabel(weekStart);
            const endLabel = formatDateLabel(weekEnd);
            const label = `Semana ${weekCount} (${startLabel} - ${endLabel})`;

            svg.append("text")
                .attr("x", xStart + 5)
                .attr("y", 20)
                .style("font-size", "11px")
                .style("fill", "#000")
                .text(label);

            current.setDate(current.getDate() + 7);
            weekCount++;
        }

        function formatDateLabel(d) {
            const day = d.getDate();
            const month = d.toLocaleString('pt-BR', { month: 'short' });
            const year = d.getFullYear();
            return `${day} ${month} ${year}`;
        }
    }

    // Adiciona linhas de grade extras, se desejado
    function addGridLines(svg, startDate, endDate) {
        const stepMs = getDynamicStep(startDate, endDate);
        let current = new Date(startDate);

        while (current <= endDate) {
            const xPos = timeScale(current);
            svg.append("line")
                .attr("x1", xPos)
                .attr("x2", xPos)
                .attr("y1", 0)
                .attr("y2", svgHeight)
                .attr("stroke", "#ccc")
                .attr("stroke-dasharray", "2,2");

            current = new Date(current.getTime() + stepMs);
        }
    }

    /**
     * Calcula o passo dinâmico baseado na diferença entre startDate e endDate.
     */
    function getDynamicStep(startDate, endDate) {
        const diffMs = endDate - startDate;
        const diffSec = diffMs / 1000;

        if (diffSec < 60) {
            return 1000;             // 1s
        } else if (diffSec < 3600) {
            return 60 * 1000;        // 1 min
        } else if (diffSec < 86400) {
            return 3600 * 1000;      // 1h
        } else if (diffSec < 604800) {
            return 86400 * 1000;     // 1 dia
        } else if (diffSec < 2592000) {
            return 7 * 86400 * 1000; // 1 semana
        } else if (diffSec < 31536000) {
            return 30 * 86400 * 1000; // ~1 mês
        }
        // >= 1 ano
        return 365 * 86400 * 1000; // ou 30 dias, de modo aproximado
    }

    // Configurações da caixa de categorias
    function setupCategoryBox(categories) {
        Object.entries(categories).forEach(([name, props]) => {
            const categoryItem = document.createElement("div");
            categoryItem.className = "category-item";
            categoryItem.innerHTML = `<span class="category-color" style="background:${props.color}"></span>${name}`;
            categoryItem.addEventListener("click", () => toggleCategory(name));
            categoryBox.appendChild(categoryItem);
        });

        function toggleCategory(name) {
            d3.selectAll(`.event-${name}`).classed("hidden", function () {
                return !d3.select(this).classed("hidden");
            });
        }
    }

    // Tooltip dos eventos (descrição)
    function showDescription(event, e) {
        eventDescription.style.display = "block";
        eventDescription.style.left = `${e.pageX + 10}px`;
        eventDescription.style.top = `${e.pageY + 10}px`;
        eventDescription.textContent = event.description || "Nenhuma descrição disponível";
    }

    function hideDescription() {
        eventDescription.style.display = "none";
    }
});
