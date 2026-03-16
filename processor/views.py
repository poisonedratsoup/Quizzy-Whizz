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
from .models import StudyGuide

load_dotenv()

HF_MODEL_URL = "https://router.huggingface.co/v1/chat/completions"


def boogie_woogie(prompt):
    HF_TOKENS = [os.getenv("HF_TOKEN_1"), os.getenv("HF_TOKEN_2")]
    MODELS = ["Qwen/Qwen2.5-Coder-32B-Instruct", "meta-llama/Meta-Llama-3-8B-Instruct"]

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
    filename = ""
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

    prompt = f"""
    Analyze the following text and extract its hierarchical structure.
    Create a nested study guide: Subject > Topic > Subtopic > Content.
    CRITICAL: DO NOT add external info, code, or examples. Use ONLY the provided text.

    HIERARCHY LOGIC:
    1. 'Subject' is the overall title of the document.
    2. 'Topics' are the major sections (usually numbered or in all-caps).
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

    try:
        choices = ai_response_data.get("choices", [])
        if isinstance(choices, list) and len(choices) > 0:
            ai_text = choices[0]["message"]["content"]
        else:
            return JsonResponse({"error": "AI response format unexpected."}, status=500)

        start_idx = ai_text.find("{")
        end_idx = ai_text.rfind("}")

        if start_idx == -1 or end_idx == -1:
            return JsonResponse(
                {"error": "AI response was not in the correct format."}, status=500
            )

        json_string = ai_text[start_idx : end_idx + 1]
        structured_data = json.loads(json_string)

        new_guide = StudyGuide.objects.create(
            subject=structured_data.get("subject", "Untitled Guide"),
            content=structured_data,
        )

        return JsonResponse({"id": new_guide.id, "data": structured_data})

    except json.JSONDecodeError:
        return JsonResponse({"error": "The AI created a broken structure."}, status=500)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
def generate_quiz(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    guide_id = request.POST.get("guide_id")
    try:

        guide = StudyGuide.objects.get(id=guide_id)

        quiz_prompt = f"""
        Based on this lesson content, generate a 5-question Multiple Choice Quiz.
        LESSON CONTENT: {json.dumps(guide.content)}
        
        STRICT JSON OUTPUT FORMAT:
        {{
            "quiz_title": "String",
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
            return JsonResponse({"error": "AI is busy, try again later"}, status=503)

        ai_text = ai_data["choices"][0]["message"]["content"]
        start, end = ai_text.find("{"), ai_text.rfind("}")
        if start == -1 or end == -1:
            return JsonResponse({"error": "Invalid AI format"}, status=500)

        return JsonResponse(json.loads(ai_text[start : end + 1]))

    except StudyGuide.DoesNotExist:
        return JsonResponse({"error": "Lesson not found"}, status=404)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
def get_all_lessons(request):
    if request.method != "GET":
        return JsonResponse({"error": "Only GET allowed"}, status=405)

    lessons = (
        StudyGuide.objects.all()
        .values("id", "subject", "created_at")
        .order_by("-created_at")
    )
    return JsonResponse(list(lessons), safe=False)


@csrf_exempt
def delete_lesson(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    guide_id = request.POST.get("guide_id")
    try:
        lesson = StudyGuide.objects.get(id=guide_id)
        lesson.delete()
        return JsonResponse({"success": True})
    except StudyGuide.DoesNotExist:
        return JsonResponse({"error": "Lesson not found"}, status=404)


@csrf_exempt
def get_lesson_detail(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    guide_id = request.POST.get("guide_id")
    try:
        lesson = StudyGuide.objects.get(id=guide_id)
        return JsonResponse(lesson.content, safe=False)
    except StudyGuide.DoesNotExist:
        return JsonResponse({"error": "Lesson not found"}, status=404)
