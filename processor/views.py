from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.views.decorators.csrf import csrf_exempt
from .models import Topic, SubTopic
from .services import (
    boogie_woogie,
    extract_text_from_file,
    calculate_difficulty,
    normalize_name,
    parse_ai_json,
)


@csrf_exempt
def home(request):
    return render(request, "index.html")


def upload_content(request):
    # Handle file upload or manual text input, process with AI, and save to DB
    if request.method != "POST":
        return redirect("/")

    file = request.FILES.get("file")
    text = extract_text_from_file(file) if file else request.POST.get("manual_text", "")

    if not text:
        return redirect("/")

    prompt = f"Analyze this text and generate flashcards. JSON ONLY: {{ 'topic_name': '', 'flashcards': [{{'front': '', 'back': ''}}] }} TEXT: {text}"
    ai_res = boogie_woogie(prompt)
    data = parse_ai_json(ai_res) if ai_res else None

    if data:
        raw_name = data.get("topic_name", "New Deck")
        clean_name = normalize_name(raw_name)
        topic_obj, _ = Topic.objects.get_or_create(name=clean_name)
        for card in data.get("flashcards", []):
            SubTopic.objects.get_or_create(
                topic=topic_obj,
                name=card.get("front", "Untitled"),
                defaults={
                    "content": card.get("back", ""),
                    "weight": calculate_difficulty(card.get("back", "")),
                },
            )
    return redirect("/")


@csrf_exempt
def get_all_lessons(request):
    # Return all topics with their subtopics and difficulty (simplified for testing)
    topics = Topic.objects.prefetch_related("subtopics").all()
    data = [{"id": t.id, "name": t.name, "difficulty": 1} for t in topics]
    return JsonResponse(data, safe=False)


@csrf_exempt
def delete_lesson(request):
    Topic.objects.filter(id=request.POST.get("guide_id")).delete()
    return JsonResponse({"success": True})


@csrf_exempt
def generate_quiz(request):
    # Generate quiz based on subtopics of a given topic
    topic = Topic.objects.filter(id=request.POST.get("guide_id")).first()
    if not topic:
        return JsonResponse({"error": "Not found"}, status=404)

    context = "\n".join([f"Q: {s.name} A: {s.content}" for s in topic.subtopics.all()])
    prompt = f"Generate a 5-question MCQ Quiz JSON based on: {context}"

    ai_res = boogie_woogie(prompt)
    data = parse_ai_json(ai_res)
    return JsonResponse(data if data else {"error": "AI Error"}, safe=False)


@csrf_exempt
def get_lesson_detail(request):
    # Return detailed info of a topic with its subtopics (simplified for testing)
    topic = Topic.objects.filter(id=request.POST.get("guide_id")).first()
    if not topic:
        return JsonResponse({"error": "Not found"}, status=404)
    return JsonResponse(
        {
            "topic_name": topic.name,
            "subtopics": list(topic.subtopics.all().values("name", "content")),
        }
    )
