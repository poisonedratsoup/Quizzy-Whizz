let selectedBatch = null;
let currentSessionSubject = null;
let activeFolder = null;

const CODESPACE_BACKEND_URL = "https://jubilant-broccoli-jw4v64rv4x9c56vv-8000.app.github.dev";

function getApiUrl(endpoint) {
    const isLocal = window.location.hostname === '127.0.0.1' || window.location.hostname === 'localhost';
    const baseUrl = isLocal ? "http://127.0.0.1:8000" : CODESPACE_BACKEND_URL;
    return `${baseUrl}${endpoint}`;
}

function showTab(tabName) {
    const createSec = document.getElementById('createSection');
    const librarySec = document.getElementById('librarySection');
    const btnCreate = document.getElementById('btnCreate');
    const btnLibrary = document.getElementById('btnLibrary');

    if (tabName === 'create') {
        createSec.style.display = 'block';
        librarySec.style.display = 'none';
        btnCreate.style.background = '#3498db';
        btnLibrary.style.background = '#95a5a6';
    } else {
        createSec.style.display = 'none';
        librarySec.style.display = 'block';
        btnCreate.style.background = '#95a5a6';
        btnLibrary.style.background = '#3498db';
        fetchLibrary();
    }
}

function setupBatches(totalUnits, unitType) {
    const unitLabel = unitType;
    document.getElementById('selectorHeader').innerHTML =
        `<p style="margin-top:0; font-weight: 600;">📄 Document has ${totalUnits} ${unitLabel}.</p>`;

    const batchContainer = document.getElementById('batchContainer');
    batchContainer.innerHTML = "";
    selectedBatch = null;

    const batchSize = (unitType === "paragraphs") ? 15 : 3;
    const totalBatches = Math.ceil(totalUnits / batchSize);

    for (let i = 0; i < totalBatches; i++) {
        const start = (i * batchSize) + 1;
        const end = Math.min((i + 1) * batchSize, totalUnits);

        const btn = document.createElement('button');
        btn.type = "button";
        const label = unitType === "pages" ? "Pg" : (unitType === "slides" ? "Slide" : "Para");
        btn.innerText = `Batch ${i + 1} (${label} ${start}-${end})`;
        btn.style.cssText = "background: #fff; color: #3498db; border: 1px solid #3498db; padding: 8px 12px; font-size: 0.85em; cursor: pointer; border-radius:6px;";

        btn.onclick = () => {
            Array.from(batchContainer.children).forEach(b => { b.style.background = "#fff"; b.style.color = "#3498db"; });
            btn.style.background = "#3498db"; btn.style.color = "#fff";
            selectedBatch = { start, end };
        };
        batchContainer.appendChild(btn);
    }
    document.getElementById('pageSelector').style.display = 'block';
}

document.getElementById('fileInput').onchange = async function () {
    localStorage.removeItem('last_processed_subject');
    if (this.files.length === 0) return;
    currentSessionSubject = null;
    const file = this.files[0];
    document.getElementById('lessonsResult').innerHTML = "";
    document.getElementById('errorBox').innerHTML = "";

    const formData = new FormData();
    formData.append('file', file);
    try {
        const res = await fetch(getApiUrl('/get_metadata/'), { method: 'POST', body: formData });
        const data = await res.json();
        setupBatches(data.total, data.type);
    } catch (e) {
        console.error("Metadata fetch failed", e);
        document.getElementById('errorBox').innerHTML = "❌ Error: Could not analyze file.";
    }
};

async function processContent() {
    const analyzeBtn = document.querySelector('button[onclick="processContent()"]');
    const fileInput = document.getElementById('fileInput');
    const manualText = document.getElementById('manualText').value;
    const manualTextValue = manualText.trim();
    const errorBox = document.getElementById('errorBox');
    const container = document.getElementById('lessonsResult');
    const formData = new FormData();

    analyzeBtn.disabled = true;
    analyzeBtn.style.opacity = "0.5";
    analyzeBtn.innerText = "Processing...";
    errorBox.innerHTML = "";

    if (manualTextValue !== "") {
        container.innerHTML = "";
        fileInput.value = "";
        document.getElementById('pageSelector').style.display = 'none';
        selectedBatch = null;
        currentSessionSubject = null;
        formData.append('manual_text', manualTextValue);

    } else if (fileInput.files.length > 0) {
        const fileObj = fileInput.files[0];
        if (!selectedBatch) {
            alert("Please select a batch first!");
            resetBtn(analyzeBtn);
            return;
        }
        formData.append('file', fileObj);
        formData.append('start_page', selectedBatch.start);
        formData.append('end_page', selectedBatch.end);
        formData.append('document_filename', fileObj.name);
    } else {
        alert("Please paste text or select a file!");
        resetBtn(analyzeBtn);
        return;
    }

    const loadingId = "loading-" + Date.now();
    container.innerHTML += `<p id="${loadingId}" style="color: #3498db; font-weight:600;">⏳ Analyzing content... Please wait.</p>`;

    const savedSubject = localStorage.getItem('last_processed_subject');
    const folderToUse = activeFolder || savedSubject;
    if (folderToUse && folderToUse !== "null") {
        formData.append('document_context', folderToUse);
    }

    try {
        const response = await fetch(getApiUrl('/upload_content/'), { method: 'POST', body: formData });
        const data = await response.json();

        if (!response.ok) throw new Error(data.error || "Server Error");

        if (data.subject) {
            localStorage.setItem('last_processed_subject', data.subject);
            activeFolder = data.subject;
            fetchLibrary();
        }

        const loadingMsg = document.getElementById(loadingId);
        if (loadingMsg) loadingMsg.remove();

        renderBatch(data);

        if (manualText.trim() !== "") {
            document.getElementById('manualText').value = "";
        }
        selectedBatch = null;

    } catch (error) {
        const loadingMsg = document.getElementById(loadingId);
        if (loadingMsg) loadingMsg.remove();
        errorBox.innerHTML = `<div class="error">❌ ${error.message}</div>`;
    } finally {
        setTimeout(() => resetBtn(analyzeBtn), 10000);

        if (analyzeBtn.disabled) {
            analyzeBtn.innerText = "Cooldown (10s)...";
        }
    }
}

function resetBtn(btn) {
    btn.disabled = false;
    btn.style.opacity = "1";
    btn.innerText = "Analyze";
}

function renderBatch(data) {
    const container = document.getElementById('lessonsResult');

    if (data.topic_name) {
        container.innerHTML = `<h1 style="color:#2c3e50; border-bottom: 2px solid #3498db; padding-bottom:10px;">${data.topic_name}</h1>`;

        if (data.subtopics) {
            data.subtopics.forEach(sub => {
                container.innerHTML += `
                    <div class="task-card" style="margin-left: 20px; border-left: 5px solid #bdc3c7;">
                        <h3 style="margin-top:0; color:#34495e;">${sub.name || sub.subtopic_name}</h3>
                        <p style="margin:0; line-height:1.6;">${sub.content}</p>
                    </div>`;
            });
        }
    }
    else if (data.subject) {
        container.innerHTML = `<h1 style="color:#2c3e50; border-bottom: 2px solid #3498db;">${data.subject}</h1>`;
        data.topics.forEach(topic => {
            container.innerHTML += `<h2 style="color:#2980b9;">📘 ${topic.topic_name}</h2>`;
            topic.subtopics.forEach(sub => {
                container.innerHTML += `
                    <div class="task-card" style="margin-left: 20px; border-left: 5px solid #bdc3c7;">
                        <h3>${sub.subtopic_name}</h3>
                        <p>${sub.content}</p>
                    </div>`;
            });
        });
    }

    container.scrollIntoView({ behavior: 'smooth', block: 'end' });
}

async function fetchLibrary() {
    const list = document.getElementById('libraryList');
    try {
        const res = await fetch(getApiUrl('/get_all_lessons/'));
        const subjects = await res.json();

        if (subjects.length === 0) {
            list.innerHTML = "<p style='padding:10px; color:#bdc3c7;'>No folders found.</p>";
            return;
        }

        list.innerHTML = "";
        subjects.forEach(subj => {
            const folderDiv = document.createElement('div');
            folderDiv.className = "folder-item";
            folderDiv.innerHTML = `<strong>📁 ${subj.subject_name}</strong>`;
            folderDiv.onclick = () => selectFolder(subj.subject_name);
            list.appendChild(folderDiv);

            subj.topics.forEach(topic => {
                const topicDiv = document.createElement('div');
                topicDiv.style.cssText = "margin-left: 15px; padding: 10px; cursor: pointer; border-radius: 6px; font-size: 0.85em; display: flex; justify-content: space-between; align-items: center; color: #ecf0f1; border-bottom: 1px solid #34495e; transition: 0.2s;";

                topicDiv.onmouseover = () => topicDiv.style.background = "#34495e";
                topicDiv.onmouseout = () => topicDiv.style.background = "transparent";

                topicDiv.onclick = () => viewLesson(topic.id);

                topicDiv.innerHTML = `
                    <span>📄 ${topic.name}</span>
                    <div style="display: flex; gap: 5px;">
                        <button onclick="event.stopPropagation(); startQuiz(${topic.id})" style="padding: 2px 6px; background: #2ecc71; font-size: 0.7em;">📝</button>
                        <button onclick="event.stopPropagation(); deleteLesson(${topic.id})" style="padding: 2px 6px; background: #e74c3c; font-size: 0.7em;">🗑️</button>
                    </div>
                `;
                list.appendChild(topicDiv);
            });
        });
    } catch (e) {
        list.innerHTML = "<p class='error'>Error loading library.</p>";
    }
}


function selectFolder(name) {
    activeFolder = name;
    document.getElementById('currentFolderName').innerText = name;
    document.getElementById('activeFolderIndicator').style.display = 'block';
    localStorage.setItem('last_processed_subject', name);
}


function createNewFolder() {
    const name = prompt("Enter New Folder Name");
    if (name && name.trim() !== "") {
        selectFolder(name.trim());
    }
}


function clearActiveFolder() {
    activeFolder = null;
    document.getElementById('activeFolderIndicator').style.display = 'none';
    localStorage.removeItem('last_processed_subject');
}

async function startQuiz(id) {
    const list = document.getElementById('libraryList');
    const originalContent = list.innerHTML;
    list.innerHTML = "<p>⏳ AI is preparing your quiz... Please wait.</p>";

    const formData = new FormData();
    formData.append('guide_id', id);

    try {
        const res = await fetch(getApiUrl('/generate_quiz/'), { method: 'POST', body: formData });
        const quiz = await res.json();
        if (!res.ok) throw new Error(quiz.error || "Server Error");

        displayQuiz(quiz);

    } catch (e) {
        alert("Quiz Error: " + e.message);
        list.innerHTML = originalContent;
    } finally {
        fetchLibrary();
    }
}

function displayQuiz(quiz) {
    document.getElementById('quizOverlay').style.display = 'block';
    document.getElementById('quizTitle').innerText = quiz.quiz_title;
    const container = document.getElementById('quizQuestions');
    container.innerHTML = "";
    document.getElementById('quizResults').innerText = "";

    quiz.questions.forEach((q, qIdx) => {
        const qDiv = document.createElement('div');
        qDiv.innerHTML = `<p><strong>${qIdx + 1}. ${q.question}</strong></p>`;

        q.options.forEach(opt => {
            const btn = document.createElement('button');
            btn.className = 'option-btn';
            btn.innerText = opt;
            btn.onclick = () => {
                const allBtns = qDiv.querySelectorAll('.option-btn');
                allBtns.forEach(b => b.disabled = true);

                if (opt === q.correct_answer) {
                    btn.classList.add('correct');
                } else {
                    btn.classList.add('wrong');
                    allBtns.forEach(b => {
                        if (b.innerText === q.correct_answer) b.classList.add('correct');
                    });
                }
            };
            qDiv.appendChild(btn);
        });
        container.appendChild(qDiv);
    });
}

function closeQuiz() {
    document.getElementById('quizOverlay').style.display = 'none';
}

async function deleteLesson(id) {
    if (!confirm("Are you sure you want to delete this lesson?")) return;

    const formData = new FormData();
    formData.append('guide_id', id);

    try {
        const res = await fetch(getApiUrl('/delete_lesson/'), { method: 'POST', body: formData });
        if (res.ok) {
            fetchLibrary();
        } else {
            alert("Failed to delete lesson.");
        }
    } catch (e) {
        console.error(e);
    }
}

async function viewLesson(id) {
    const container = document.getElementById('lessonsResult');
    container.innerHTML = "<p>⏳ Loading...</p>";

    const formData = new FormData();
    formData.append('guide_id', id);

    try {
        const res = await fetch(getApiUrl('/get_lesson_detail/'), { method: 'POST', body: formData });
        const topicData = await res.json();

        container.innerHTML = `<h1 style="color:#2c3e50; border-bottom: 2px solid #3498db;">${topicData.topic_name}</h1>`;
        topicData.subtopics.forEach(sub => {
            container.innerHTML += `
                <div class="task-card" style="margin-left: 20px; border-left: 5px solid #bdc3c7;">
                    <h3 style="margin-top:0;">${sub.name}</h3>
                    <p>${sub.content}</p>
                </div>`;
        });
    } catch (e) {
        container.innerHTML = "<p class='error'>Failed to load.</p>";
    }
}

window.onload = () => {
    fetchLibrary();
    const saved = localStorage.getItem('last_processed_subject');
    if (saved) selectFolder(saved);
};