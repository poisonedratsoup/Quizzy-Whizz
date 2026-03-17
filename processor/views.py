import json
import os
import time
import docx
import pdfplumber
import requests
from dotenv import load_dotenv
from pptx import Presentation
from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from .models import Subject, Topic, SubTopic

load_dotenv()

HF_MODEL_URL = "https://router.huggingface.co/v1/chat/completions"


def boogie_woogie(prompt):
    HF_TOKENS = [os.getenv("HF_TOKEN_1"), os.getenv("HF_TOKEN_2")]
    MODELS = [
        "Qwen/Qwen2.5-Coder-32B-Instruct",
        "deepseek-ai/DeepSeek-V3",
        "deepseek-ai/DeepSeek-R1-Distill-Qwen-32B",
    ]

    payload = {
        "messages": [
            {
                "role": "system",
                "content": "You are a helpful tutor that outputs ONLY valid JSON.",
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.0,
    }

    for token in HF_TOKENS:
        if not token:
            continue
        for model_name in MODELS:
            payload["model"] = model_name
            try:
                print(f"Quiz Attempt: {model_name} | Token {HF_TOKENS.index(token)+1}")
                res = requests.post(
                    HF_MODEL_URL,
                    headers={"Authorization": f"Bearer {token}"},
                    json=payload,
                    timeout=(10, 120),
                )
                if res.status_code == 200:
                    return res.json()
                if res.status_code == 402:
                    break
                time.sleep(2)
            except:
                continue
    return None


def calculate_difficulty(text):
    words = text.split()
    length_score = 1
    if len(words) > 1000:
        length_score = 3
    elif len(words) > 400:
        length_score = 2

    complex_terms = [
        "theory",
        "algorithm",
        "derivation",
        "formula",
        "analysis",
        "synthesis",
        "calculus",
        "protocol",
        "framework",
    ]
    found_terms = sum(1 for term in complex_terms if term in text.lower())

    complexity_score = 2 if found_terms > 4 else 1

    return min(length_score + complexity_score, 5)


@csrf_exempt
def get_metadata(request):
    if request.method != "POST":
        return JsonResponse({"error": "Only POST allowed"}, status=405)

    if "file" not in request.FILES:
        return JsonResponse({"error": "No file"}, status=400)

    file = request.FILES["file"]
    filename = file.name.lower()

    try:
        if filename.endswith(".pdf"):
            with pdfplumber.open(file) as pdf:
                return JsonResponse({"total": len(pdf.pages), "type": "pages"})
        elif filename.endswith(".docx"):
            doc = docx.Document(file)
            count = sum(1 for p in doc.paragraphs if p.text.strip())
            return JsonResponse({"total": count, "type": "paragraphs"})
        elif filename.endswith(".pptx"):
            prs = Presentation(file)
            return JsonResponse({"total": len(prs.slides), "type": "slides"})
    except Exception as e:
        return JsonResponse({"error": f"Could not read file: {str(e)}"}, status=500)


@csrf_exempt
def home(request):
    return render(request, "index.html")


@csrf_exempt
def upload_content(request):
    if request.method != "POST":
        return JsonResponse({"error": "Only POST allowed"}, status=405)

    text = ""
    context_subject = request.POST.get("document_context", "").strip()
    try:
        start_val = int(request.POST.get("start_page", 1))
        end_val = int(request.POST.get("end_page", 3))
        start_pg, end_pg = max(0, start_val - 1), end_val
    except ValueError:
        start_pg, end_pg = 0, 3

    if "file" in request.FILES:
        file = request.FILES["file"]
        if file.name == "":
            return JsonResponse({"error": "No file selected"}, status=400)
        filename = file.name.lower()

        try:
            if filename.endswith(".pdf"):
                with pdfplumber.open(file) as pdf:
                    actual_end = min(end_pg, len(pdf.pages))
                    text = "\n".join(
                        [
                            p.extract_text()
                            for p in pdf.pages[start_pg:actual_end]
                            if p.extract_text()
                        ]
                    )

            elif filename.endswith(".docx"):
                doc = docx.Document(file)
                paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
                text = "\n".join(paragraphs[start_pg:end_pg])

            elif filename.endswith(".pptx"):
                prs = Presentation(file)
                selected_slides = list(prs.slides)[start_pg:end_pg]
                full_text = []
                for slide in selected_slides:
                    for shape in slide.shapes:
                        if hasattr(shape, "text") and shape.text.strip():
                            full_text.append(shape.text.strip())
                text = "\n".join(full_text)
        except Exception as e:
            return JsonResponse({"error": f"Extraction failed: {str(e)}"}, status=500)

    elif "manual_text" in request.POST:
        text = request.POST["manual_text"]

    text = text.replace("\x00", "").strip()[:12000]
    if not text.strip():
        return JsonResponse({"error": "No text found to process."}, status=400)

    context_instruction = (
        f"IMPORTANT: This is a continuation of the document: '{context_subject}'. Keep the 'subject' field as '{context_subject}'."
        if context_subject
        else "Identify the overall Subject of this text."
    )

    prompt = f"""
    Analyze this PARTIAL text from a document. {context_instruction}
    Create a nested study guide: Subject > Topic > Subtopic > Content.
    CRITICAL: DO NOT add external info, code, or examples. Use ONLY the provided text.

    HIERARCHY LOGIC:
    1. 'Subject' is the overall title of the document.
    2. 'Topics' are the major sections (usually numbered or in all-caps). If a topic spans multiple batches, use the SAME 'topic_name'.
    3. 'Subtopics' are the specific concepts discussed within a topic.
    4. 'Content' is the explanation or definition for that specific subtopic.
    5. IMPORTANT: If a list of items has NO individual descriptions in the text, DO NOT make them separate subtopics. Instead, group them into a single Subtopic called "Key Concepts" or "Overview".

    STRICT JSON OUTPUT:
    {{
    "subject": "String",
    "topics": [
        {{
        "topic_name": "String",
        "subtopics": [
            {{ "subtopic_name": "String", "content": "String" }}
        ]
        }}
    ]
    }}

    TEXT TO PROCESS:
    {text}
    """

    ai_response_data = boogie_woogie(prompt)

    if not ai_response_data:
        return JsonResponse(
            {"error": "All AI models are currently overwhelmed. Please wait a moment."},
            status=503,
        )
    client_filename = (
        request.FILES.get("file").name if "file" in request.FILES else "Manual Upload"
    )

    try:
        ai_text = ai_response_data["choices"][0]["message"]["content"]
        start_idx, end_idx = ai_text.find("{"), ai_text.rfind("}")
        structured_data = json.loads(ai_text[start_idx : end_idx + 1])

        ai_subj_name = structured_data.get("subject", "General Studies")
        if (
            context_subject
            and context_subject.lower() != "null"
            and context_subject != ""
        ):
            final_subject_name = context_subject
        else:
            final_subject_name = ai_subj_name

        subj_obj, _ = Subject.objects.get_or_create(name=final_subject_name)

        last_topic_obj = None
        for t_data in structured_data.get("topics", []):
            t_name = t_data.get("topic_name", "Untitled Topic")

            topic_obj, _ = Topic.objects.get_or_create(subject=subj_obj, name=t_name)
            last_topic_obj = topic_obj

            for s_data in t_data.get("subtopics", []):
                sub_name = s_data.get("subtopic_name", "General Concept")
                sub_content = s_data.get("content", "")

                if not SubTopic.objects.filter(topic=topic_obj, name=sub_name).exists():
                    SubTopic.objects.create(
                        topic=topic_obj,
                        name=sub_name,
                        content=sub_content,
                        weight=calculate_difficulty(sub_content),
                    )

        return JsonResponse(
            {
                "subject": subj_obj.name,
                "topic_name": last_topic_obj.name if last_topic_obj else "Uploaded",
                "subtopics": list(
                    last_topic_obj.subtopics.all().values("name", "content")
                ),
            }
        )

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
def generate_quiz(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    topic_id = request.POST.get("guide_id")
    try:
        topic = Topic.objects.get(id=topic_id)
        subtopics = topic.subtopics.all()

        lesson_context = "\n".join(
            [f"Subtopic: {s.name}\nContent: {s.content}" for s in subtopics]
        )

        quiz_prompt = f"""
        Based on this lesson content, generate a 5-question Multiple Choice Quiz.
        LESSON CONTENT: {lesson_context}
        
        STRICT JSON OUTPUT FORMAT:
        {{
            "quiz_title": "{topic.name} Quiz",
            "questions": [
                {{
                    "question": "String",
                    "options": ["A", "B", "C", "D"],
                    "correct_answer": "Exact string from options"
                }}
            ]
        }}
        """

        ai_data = boogie_woogie(quiz_prompt)
        if not ai_data:
            return JsonResponse({"error": "AI is busy"}, status=503)

        ai_text = ai_data["choices"][0]["message"]["content"]
        start, end = ai_text.find("{"), ai_text.rfind("}")
        return JsonResponse(json.loads(ai_text[start : end + 1]))

    except Topic.DoesNotExist:
        return JsonResponse({"error": "Topic not found"}, status=404)


@csrf_exempt
def get_all_lessons(request):
    subjects = Subject.objects.prefetch_related("topics__subtopics").all()

    library_data = []
    for s in subjects:
        topics_list = []
        for t in s.topics.all():
            sub_weights = [st.weight for st in t.subtopics.all()]
            avg_weight = sum(sub_weights) // len(sub_weights) if sub_weights else 1

            topics_list.append({"id": t.id, "name": t.name, "difficulty": avg_weight})

        library_data.append({"subject_name": s.name, "topics": topics_list})

    return JsonResponse(library_data, safe=False)


@csrf_exempt
def delete_lesson(request):
    topic_id = request.POST.get("guide_id")
    try:
        topic = Topic.objects.get(id=topic_id)
        subject = topic.subject
        topic.delete()
        if not subject.topics.exists():
            subject.delete()
        return JsonResponse({"success": True})
    except Topic.DoesNotExist:
        return JsonResponse({"error": "Topic not found"}, status=404)


@csrf_exempt
def get_lesson_detail(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    topic_id = request.POST.get("guide_id")
    try:
        topic = Topic.objects.get(id=topic_id)

        subtopics = topic.subtopics.all().values("name", "content", "weight")

        response_data = {"topic_name": topic.name, "subtopics": list(subtopics)}

        return JsonResponse(response_data, safe=False)

    except Topic.DoesNotExist:
        return JsonResponse({"error": "Topic not found"}, status=404)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
