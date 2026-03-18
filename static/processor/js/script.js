let selectedBatch = null;
let activeFolder = localStorage.getItem('last_processed_subject') || null;

// API URL Helper
function getApiUrl(endpoint) {
    const isLocal = window.location.hostname === '127.0.0.1' || window.location.hostname === 'localhost';
    const baseUrl = isLocal ? "http://127.0.0.1:8000" : "https://jubilant-broccoli-jw4v64rv4x9c56vv-8000.app.github.dev";
    return `${baseUrl}${endpoint}`;
}

// Sidebar/Folder UI Logic
function updateActiveFolderUI() {
    const banner = document.getElementById('activeFolderIndicator');
    const nameSpan = document.getElementById('currentFolderName');
    if (activeFolder && activeFolder !== "null") {
        banner.style.display = 'block';
        nameSpan.innerText = activeFolder;
    } else {
        banner.style.display = 'none';
    }
}

function clearActiveFolder() {
    activeFolder = null;
    localStorage.removeItem('last_processed_subject');
    updateActiveFolderUI();
}

// File Upload & Metadata Extraction
document.getElementById('fileInput').onchange = async function () {
    if (this.files.length === 0) return;

    const file = this.files[0];
    const formData = new FormData();
    formData.append('file', file);

    try {
        const res = await fetch(getApiUrl('/get_metadata/'), { method: 'POST', body: formData });
        const data = await res.json();
        setupBatches(data.total, data.type);
    } catch (e) {
        document.getElementById('errorBox').innerHTML = "❌ Error: Could not analyze file.";
    }
};

// Batch Selection UI
function setupBatches(totalUnits, unitType) {
    const container = document.getElementById('batchContainer');
    document.getElementById('selectorHeader').innerHTML = `<strong>📄 ${totalUnits} ${unitType} found.</strong>`;
    container.innerHTML = "";
    document.getElementById('pageSelector').style.display = 'block';

    const batchSize = (unitType === "paragraphs") ? 15 : 3;
    const totalBatches = Math.ceil(totalUnits / batchSize);

    for (let i = 0; i < totalBatches; i++) {
        const start = (i * batchSize) + 1;
        const end = Math.min((i + 1) * batchSize, totalUnits);
        const btn = document.createElement('button');
        btn.innerText = `Batch ${i + 1} (${start}-${end})`;
        btn.style.margin = "5px";

        btn.onclick = () => {
            // Just remove "active" from everyone and give it to THIS button
            document.querySelectorAll('.batch-btn').forEach(b => b.classList.remove('active-batch'));
            btn.classList.add('active-batch');
            selectedBatch = { start, end };
        };
        container.appendChild(btn);
    }
}

// Main Process Logic
async function processContent() {
    const btn = document.getElementById('analyzeBtn');
    const fileInput = document.getElementById('fileInput');
    const manualText = document.getElementById('manualText').value.trim();

    if (!manualText && !fileInput.files[0]) return alert("Please provide content!");
    if (fileInput.files[0] && !selectedBatch) return alert("Select a batch!");

    btn.disabled = true;
    btn.innerText = "⏳ Processing...";

    const formData = new FormData();
    if (manualText) formData.append('manual_text', manualText);
    else {
        formData.append('file', fileInput.files[0]);
        formData.append('start_page', selectedBatch.start);
        formData.append('end_page', selectedBatch.end);
    }

    if (activeFolder) formData.append('document_context', activeFolder);

    try {
        const res = await fetch(getApiUrl('/upload_content/'), { method: 'POST', body: formData });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error);

        activeFolder = data.subject;
        localStorage.setItem('last_processed_subject', data.subject);
        updateActiveFolderUI();
        renderBatch(data);
        fetchLibrary();

    } catch (e) {
        alert("Error: " + e.message);
    } finally {
        btn.disabled = false;
        btn.innerText = "Analyze";
    }
}

// Render Lessons/Study Mode
function renderBatch(data) {
    const container = document.getElementById('lessonsResult');
    let html = `<h1>${data.topic_name}</h1>`;

    data.subtopics.forEach(sub => {
        html += `
            <div class="task-card">
                <h3>${sub.name}</h3>
                <p>${sub.content}</p>
            </div>`;
    });

    container.innerHTML = html;

    container.scrollIntoView({ behavior: 'smooth', block: 'end' });
}

updateActiveFolderUI();

// Library Management
async function fetchLibrary() {
    const list = document.getElementById('libraryList');
    try {
        const res = await fetch(getApiUrl('/get_all_lessons/'));
        const subjects = await res.json();

        if (subjects.length === 0) {
            list.innerHTML = "<p style='color:#bdc3c7;'>No folders found.</p>";
            return;
        }

        list.innerHTML = "";
        subjects.forEach(subj => {
            // Subject Folder
            const folderDiv = document.createElement('div');
            folderDiv.className = "folder-item";
            folderDiv.innerHTML = `<strong>📁 ${subj.subject_name}</strong>`;
            folderDiv.onclick = () => selectFolder(subj.subject_name);
            list.appendChild(folderDiv);

            // Topics inside Folder
            subj.topics.forEach(topic => {
                const topicDiv = document.createElement('div');
                topicDiv.className = "sidebar-topic"; // Uses your CSS hover/padding
                topicDiv.onclick = () => viewLesson(topic.id);

                topicDiv.innerHTML = `
                    <span>📄 ${topic.name}</span>
                    <div class="sidebar-actions">
                        <button onclick="event.stopPropagation(); startQuiz(${topic.id})" class="btn-sm-green">📝</button>
                        <button onclick="event.stopPropagation(); deleteLesson(${topic.id})" class="btn-sm-red">🗑️</button>
                    </div>
                `;
                list.appendChild(topicDiv);
            });
        });
    } catch (e) {
        list.innerHTML = "<p>Error loading library.</p>";
    }
}

// Folder Selection Logic
function selectFolder(name) {
    activeFolder = name;
    document.getElementById('currentFolderName').innerText = name;
    document.getElementById('activeFolderIndicator').style.display = 'block';
    localStorage.setItem('last_processed_subject', name);
}

// New Folder Creation
function createNewFolder() {
    const name = prompt("Enter New Folder Name");
    if (name && name.trim() !== "") {
        selectFolder(name.trim());
    }
}

// Clear Active Folder
function clearActiveFolder() {
    activeFolder = null;
    document.getElementById('activeFolderIndicator').style.display = 'none';
    localStorage.removeItem('last_processed_subject');
}

// Quiz Logic
async function startQuiz(id) {
    const overlay = document.getElementById('quizOverlay');
    const questionsBox = document.getElementById('quizQuestions');

    overlay.style.display = 'block';
    questionsBox.innerHTML = "<p>⏳ AI is preparing your quiz... Please wait.</p>";
    document.getElementById('quizTitle').innerText = "Generating...";

    const formData = new FormData();
    formData.append('guide_id', id);

    try {
        const res = await fetch(getApiUrl('/generate_quiz/'), { method: 'POST', body: formData });
        const quiz = await res.json();
        if (!res.ok) throw new Error(quiz.error);

        displayQuiz(quiz);
    } catch (e) {
        alert("Quiz Error: " + e.message);
        closeQuiz();
    }
}

// Display Quiz Questions
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

// Close Quiz Overlay
function closeQuiz() {
    document.getElementById('quizOverlay').style.display = 'none';
}

// Delete Lesson Logic
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

// View Lesson Detail Logic
async function viewLesson(id) {
    const container = document.getElementById('lessonsResult');
    container.innerHTML = "<p>⏳ Loading...</p>";

    const formData = new FormData();
    formData.append('guide_id', id);

    try {
        const res = await fetch(getApiUrl('/get_lesson_detail/'), { method: 'POST', body: formData });
        const data = await res.json();

        let html = `<h1>${data.topic_name}</h1>`;
        data.subtopics.forEach(sub => {
            html += `
                <div class="task-card">
                    <h3>${sub.name}</h3>
                    <p>${sub.content}</p>
                </div>`;
        });
        container.innerHTML = html;
        container.scrollTop = 0;
    } catch (e) {
        container.innerHTML = "<p>Failed to load lesson.</p>";
    }
}

window.onload = () => {
    fetchLibrary();
    const saved = localStorage.getItem('last_processed_subject');
    if (saved) selectFolder(saved);
};