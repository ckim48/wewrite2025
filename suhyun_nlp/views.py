from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.hashers import make_password
from django.http import JsonResponse, HttpResponse
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt

from story.models import *

from member.models import *  # Importing CustomUser model from manager app

from openai import OpenAI

def translate_text_to_korean(text):
    res = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "Translate the following story to Korean:"},
            {"role": "user", "content": text}
        ]
    )
    return res.choices[0].message.content.strip()

def to_index(request):
    is_login = request.user.is_authenticated
    is_admin = request.user.is_staff if is_login else False
    username = request.user.username if is_login else ""

    context = {
        'isLogin': is_login,
        'isAdmin': is_admin,
        'username': username,
    }

    return render(request, 'index.html', context)


def to_login(request):
    # Redirect to student-main page if user is already authenticated
    # if request.user.is_authenticated:
    #     return redirect('member-main')

    # Handling form submission
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')

        try:
            user = CustomUser.objects.get(username=email)
            authenticated_user = authenticate(request, username=email, password=password)
            print("user authenticated")

            # If authentication successful, login user
            if authenticated_user:
                print("user authenticated")
                login(request, authenticated_user)
                print("user logged in")
                return redirect('to-main')
            else:
                messages.error(request, "Invalid login credentials")
                print("Invalid credentials")
                return redirect('to-login')

        except CustomUser.DoesNotExist:
            # Handle non-existing user
            messages.error(request, "User does not exist")
            print("User does not exist")
            return redirect('to-login')

    # Render login page if request method is GET
    return render(request, 'login.html', {})

@login_required
def to_logout(request):
    logout(request)
    return redirect('to-index')
def to_signup(request):
    # Handling form submission
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        password_confirm = request.POST.get('passwordconfirm')


        # Check if username already exists
        if CustomUser.objects.filter(username=email).exists():
            messages.error(request, "Username already exists!")
            return redirect('to-signup')

        # Check if all required fields are filled
        if not all([email, password, password_confirm]):
            messages.error(request, "Please fill out all the required fields!")
            return redirect('to-signup')

        # Check if password matches confirm password
        if password == password_confirm:
            # Hash password and create new user
            hashed_password = make_password(password)
            new_user = CustomUser(
                username=email,
                password=hashed_password,
            )
            new_user.save()
            messages.success(request, "User added successfully!")

            return redirect('to-login')

        else:
            messages.error(request, "Password doesn't match. Please try again!")
            return redirect('to-signup')

    return render(request, 'signup.html')


@login_required
def to_write(request):
    import datetime

    curr_user = request.user
    username = curr_user.username

    genre_list = Genre.objects.filter(is_active=True)

    genre_name_list = ['Fiction', 'Science Fiction', 'Historical Fiction', 'Mystery', 'Fantasy', 'Romance']

    isAdmin= curr_user.is_staff

    context = {
        'username': username,
        'isLogin': True,
        'genre_name_list': genre_name_list,
        'isAdmin': isAdmin,

    }

    if request.method == 'POST':
        print("POSTED")
        user = CustomUser.objects.get(username=curr_user.username)
        title = request.POST.get('title')

        selected_genre_names = request.POST.getlist('selected_genre[]')  # get all selected genres as list
        print(selected_genre_names)
        if not selected_genre_names:
            print(request, "Please select at least one genre.")
            return redirect('to-write')

        genre_name = selected_genre_names[0]
        try:
            print(genre_name)
            genre = Genre.objects.get(name=genre_name)
        except Genre.DoesNotExist:
            print(request, "Selected genre(s) not found in database.")
            return redirect('to-write')

        maincharacter = request.POST.get('maincharacter')
        timesetting = request.POST.get('timesetting')
        exposition = request.POST.get('exposition')

        today_year = str(datetime.datetime.today().year)
        today_month = str(datetime.datetime.today().month)
        today_day = str(datetime.datetime.today().day)

        started_date = "-".join([today_year, today_month, today_day])

        from keybert import KeyBERT
        kw_model = KeyBERT()
        keywords_mmr = kw_model.extract_keywords(exposition, keyphrase_ngram_range=(1, 1), stop_words='english',
                                                 use_mmr=True,
                                                 top_n=5, diversity=0.3)
        keyword_list = [km[0] for km in keywords_mmr]  # ['a', 'b', 'c', 'd', 'e']

        suggested_keyword = ", ".join(keyword_list)

        from transformers import pipeline

        # 요약 파이프라인 생성
        summarizer = pipeline("summarization", model="facebook/bart-large-cnn")
        # 요약 실행
        print("")
        summary = summarizer(exposition, max_length=100, min_length=10, do_sample=False)

        exposition_summary = summary[0]['summary_text']

        new_story = Story(
            user=user,
            started_date = started_date,
            title = title,
            genre = genre,
            main_character = maincharacter,
            time_setting = timesetting,
            suggested_keyword = suggested_keyword,
            exposition_summary = exposition_summary,
        )
        new_story.save()

        new_stage = Stage(
            story=new_story,
            user = user,
            submitted_date = started_date,
            part = 1,
            status = 1,
            text = exposition,
        )
        new_stage.save()

        return redirect('to-main')

    return render(request, 'write.html', context)

@login_required
def to_main(request):
    curr_user = request.user
    username = curr_user.username
    isAdmin = curr_user.is_staff

    author_stages = Stage.objects.filter(user=curr_user, status=3)
    if len(author_stages)>=0:
        new_story_available = True
    else:
        new_story_available = False

    all_storys = Story.objects.all().order_by('started_date')

    story_list = []
    story_last_stage_part_list = []
    all_stages = list(Stage.objects.all().order_by('pk'))
    for story in all_storys:
        curr_story_stage_list = []
        for all_stage in all_stages:
            if all_stage.story == story:
                curr_story_stage_list.append(all_stage)

        if not curr_story_stage_list:
            continue  # skip if no stages yet

        if len(curr_story_stage_list) == 5:
            continue  # completed

        # check if there's at least one accepted stage
        if not any(stage.status == 3 for stage in curr_story_stage_list):
            continue  # not started properly

        story_list.append(story)
        story_last_stage_part_list.append(curr_story_stage_list[-1].PART_CHOICES[curr_story_stage_list[-1].part][1])

    story_exposition_list = [story.exposition_summary for story in story_list]
    # print(story_exposition_list)
    story_pk_list = [story.pk for story in story_list]
    story_genre_list = [story.genre for story in story_list]
    story_title_list = [story.title for story in story_list]


    all_genres = Genre.objects.all().order_by('pk')
    all_genres_pk_list = [genre.pk for genre in all_genres]

    story_tuple_list = [] # (story , exposition, pk, genre, title)
    for i in range(len(story_list)):
        story_tuple_list.append((story_list[i], story_exposition_list[i], story_pk_list[i], story_genre_list[i], story_title_list[i], story_last_stage_part_list[i]))
    print(story_tuple_list)
    context = {
        'username': username,
        'isLogin': True,
        'isAdmin': isAdmin,
        'story_list': story_list,
        'story_exposition_list': story_exposition_list,
        'story_pk_list': story_pk_list,
        'story_genre_list': story_genre_list,
        'story_title_list': story_title_list,
        'story_tuple_list': story_tuple_list,
        'new_story_available': new_story_available,
        'all_genres': all_genres
    }
    return render(request, 'main.html', context)
@login_required
def to_read(request):
    from pathlib import Path
    import os, pickle
    from numpy import dot
    from numpy.linalg import norm

    curr_user = request.user
    isAdmin = curr_user.is_staff
    username = curr_user.username

    all_storys = Story.objects.all().order_by('started_date')
    accepted_stages = list(Stage.objects.filter(status=3).order_by('pk'))

    all_stories = []
    for story in all_storys:
        accepted_for_story = [s for s in accepted_stages if s.story_id == story.id]
        if len(accepted_for_story) == 5:
            all_stories.append(story)

    story_list = all_stories

    all_stages = list(Stage.objects.all().order_by('pk'))

    # Get authors for each story
    story_author_list = []
    for story in story_list:
        curr_story_author_list = []
        for stage in all_stages:
            if stage.story == story:
                author_display_name = stage.user.name or stage.user.username
                curr_story_author_list.append(author_display_name)
        story_author_list.append(", ".join(curr_story_author_list))

    story_pk_list = [story.pk for story in story_list]
    story_genre_list = [story.genre for story in story_list]
    story_title_list = [story.title for story in story_list]

    story_tuple_list = []
    for i in range(len(story_list)):
        story_tuple_list.append((story_list[i], story_author_list[i], story_pk_list[i], story_genre_list[i], story_title_list[i]))

    # --- Recommendation logic ---
    BASE_DIR = Path(__file__).resolve().parent.parent
    picklefile_name = os.path.join(BASE_DIR, 'static', 'pickle', f'{curr_user.pk}.pickle')

    if os.path.isfile(picklefile_name):
        with open(picklefile_name, 'rb') as f:
            user_history_dict = pickle.load(f)
    else:
        user_history_dict = {
            'genre_pk_list': [],
            'genre_cnt_list': []
        }

    all_genres = Genre.objects.all().order_by('pk')
    all_genres_pk_list = [genre.pk for genre in all_genres]

    genre_vector_list = []
    for idx in range(len(all_genres)):
        vector = [0] * len(all_genres)
        vector[idx] = 1
        genre_vector_list.append(vector)

    user_vector = [0] * len(all_genres)
    for idx, gpk in enumerate(user_history_dict['genre_pk_list']):
        if gpk in all_genres_pk_list:
            genre_idx = all_genres_pk_list.index(gpk)
            user_vector[genre_idx] += user_history_dict['genre_cnt_list'][idx]

    all_story_vector_list = []
    all_story_genre_pk_list = [story.genre.pk for story in all_stories]
    for pk in all_story_genre_pk_list:
        idx = all_genres_pk_list.index(pk)
        all_story_vector_list.append(genre_vector_list[idx])

    def cosine_similarity(vec1, vec2):
        return dot(vec1, vec2) / (norm(vec1) * norm(vec2)) if norm(vec1) > 0 and norm(vec2) > 0 else 0.0

    all_story_similarity_list = [cosine_similarity(user_vector, sv) for sv in all_story_vector_list]
    all_story_tuple_list = list(zip(all_stories, all_story_similarity_list))
    sorted_data = sorted(all_story_tuple_list, key=lambda x: x[1], reverse=True)
    recommended_story_list = [s[0] for s in sorted_data[:4]]

    recommended_story_tuple_list = []
    for story in recommended_story_list:
        authors = []
        for stage in all_stages:
            if stage.story == story:
                name = stage.user.name or stage.user.username
                short_name = name.split('@')[0]
                authors.append(short_name)
        genre_slug = story.genre.name.lower().replace(' ', '')
        recommended_story_tuple_list.append((
            story, ", ".join(authors), story.pk, story.genre, story.title, genre_slug
        ))

    formatted_list = []
    for story, author, pk, genre, title in story_tuple_list:
        username = author.split('@')[0]
        genre_slug = genre.name.lower().replace(" ", "")
        formatted_list.append((story, username, pk, genre, title, genre_slug))
    context = {
        'username': username,
        'isLogin': True,
        'isAdmin': isAdmin,
        "story_tuple_list": formatted_list,
        'recommended_story_tuple_list': recommended_story_tuple_list,
        'story_list': story_list,
        'story_exposition_list': story_author_list,
        'story_pk_list': story_pk_list,
        'story_genre_list': story_genre_list,
        'story_title_list': story_title_list,
        'all_genres': all_genres
    }

    return render(request, 'read.html', context)
@login_required
def to_detail(request, id):
    import os, pickle
    from pathlib import Path

    curr_user = request.user
    isAdmin = curr_user.is_staff
    username = curr_user.username

    # Get the story and related stages
    curr_story = get_object_or_404(Story, pk=id)
    curr_story_stages = Stage.objects.filter(story=curr_story).order_by('part')
    curr_story_author_list = [stage.user.username for stage in curr_story_stages]
    curr_story_authors = ", ".join(curr_story_author_list)

    # Load or initialize user reading history
    BASE_DIR = Path(__file__).resolve().parent.parent
    picklefile_name = os.path.join(BASE_DIR, 'static', 'pickle', f'{curr_user.pk}.pickle')
    if os.path.isfile(picklefile_name):
        with open(picklefile_name, 'rb') as f:
            user_history_dict = pickle.load(f)
    else:
        user_history_dict = {'genre_pk_list': [], 'genre_cnt_list': []}

    # Update user reading history
    curr_genre_pk = curr_story.genre.pk
    if curr_genre_pk in user_history_dict['genre_pk_list']:
        idx = user_history_dict['genre_pk_list'].index(curr_genre_pk)
        user_history_dict['genre_cnt_list'][idx] += 1
    else:
        user_history_dict['genre_pk_list'].append(curr_genre_pk)
        user_history_dict['genre_cnt_list'].append(1)

    with open(picklefile_name, 'wb') as f:
        pickle.dump(user_history_dict, f)

    # Handle comment form submission
    if request.method == "POST":
        comment_text = request.POST.get("comment_text")
        if comment_text:
            Comment.objects.create(
                story=curr_story,
                user=curr_user,
                text=comment_text,
            )
            return redirect('to-detail', id=curr_story.id)

    # Load all comments for the story
    comments = Comment.objects.filter(story=curr_story).order_by('-created_at')
    full_text = "\n".join([stage.text for stage in curr_story_stages])
    translated_korean = translate_text_to_korean(full_text)
    context = {
        'isAdmin': isAdmin,
        'username': username,
        'isLogin': True,
        'curr_story': curr_story,
        'translated_korean': translated_korean,
        'curr_story_stages': curr_story_stages,
        'curr_story_authors': curr_story_authors,
        'comments': comments,
    }

    return render(request, 'detail.html', context)


@login_required
def delete_comment(request, comment_id):
    comment = get_object_or_404(Comment, id=comment_id)

    if request.user == comment.user or request.user.is_staff:
        story_id = comment.story.id
        comment.delete()
        return redirect('to-detail', id=story_id)

    return redirect('to-detail', id=comment.story.id)


from django.http import HttpResponse
from django.utils.text import slugify


@login_required
def download_text(request, id):
    story = get_object_or_404(Story, pk=id)
    lang = request.GET.get("lang", "en")
    if lang == "ko":
        # Use GPT-translated Korean version
        full_text = translate_text_to_korean("\n".join([s.text for s in Stage.objects.filter(story=story).order_by('part')]))
    else:
        full_text = f"{story.title}\n\n"
        for stage in Stage.objects.filter(story=story).order_by('part'):
            full_text += f"--- Part {stage.part} ---\n{stage.text}\n\n"

    filename = f"{slugify(story.title)}_{lang}.txt"
    response = HttpResponse(full_text, content_type='text/plain')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response

from gtts import gTTS
from django.http import FileResponse
import tempfile

@login_required
def download_audio(request, id):
    story = get_object_or_404(Story, pk=id)
    lang = request.GET.get("lang", "en")

    if lang == "ko":
        text = translate_text_to_korean("\n".join([s.text for s in Stage.objects.filter(story=story).order_by('part')]))
        lang_code = "ko"
    else:
        text = f"{story.title}\n\n" + "\n".join([s.text for s in Stage.objects.filter(story=story).order_by('part')])
        lang_code = "en"

    tts = gTTS(text=text, lang=lang_code)
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    tts.save(temp_file.name)

    filename = f"{slugify(story.title)}_{lang}.mp3"
    return FileResponse(open(temp_file.name, 'rb'), as_attachment=True, filename=filename)



@login_required
def to_collaborate(request, id):
    curr_user = request.user
    isAdmin = curr_user.is_staff
    curr_story = Story.objects.get(pk=id)

    curr_story_stages = Stage.objects.filter(story=curr_story).order_by('part')

    # Calculate the current part to be written (next part)
    curr_part = len(curr_story_stages) + 1
    if curr_part > 5:
        curr_part = 5  # Cap at 5 (Resolution)

    context = {
        'isAdmin': isAdmin,
        'curr_story': curr_story,
        'curr_story_stages': curr_story_stages,
        'pk': curr_story.pk,
        'isLogin': True,
        'curr_part': curr_part,  # ✅ Add this
    }

    if request.method == 'POST':
        curr_text = request.POST.get('text')
        import datetime
        today = datetime.datetime.today().strftime("%Y-%m-%d")

        new_stage = Stage(
            story=curr_story,
            user=curr_user,
            submitted_date=today,
            part=curr_part,
            status=3,
            text=curr_text,
        )
        new_stage.save()
        return redirect('to-main')

    return render(request, 'collaborate.html', context)


@login_required
def to_inprogress(request):
    curr_user = request.user
    isAdmin = curr_user.is_staff
    username = curr_user.username

    if request.method == 'POST':
        curr_user = request.user

        status = request.POST.get('status')
        pk = request.POST.get('pk')
        # print(pk)
        # print(status)

        status_dict = {
            'Pending': 1,
            'Rejected': 2,
            'Accepted': 3,
        }

        curr_stage = Stage.objects.get(pk=pk)
        curr_stage.status = status_dict[status]
        #TODO:My Submissions 추가되고 나면 기각사유와 기각코드 저장하게 변경하기(models에서 필드도 생성해야함)
        curr_stage.save()

        return redirect('to-inprogress')

    pending_stages = list(Stage.objects.filter(status='1').order_by('pk'))
    pending_stage_part_list = [stage.PART_CHOICES[stage.part-1][1] for stage in pending_stages]
    # for story in story_list:
    #     curr_story_author_list = []
    #     for stage in all_stages:
    #         if stage.story == story:
    #             curr_story_author_list.append(stage.user.name)
    #             #curr_story_author_list.append(stage.user.username)
    #     story_author_list.append(", ".join(curr_story_author_list))
    # story_pk_list = [story.pk for story in story_list]
    # story_genre_list = [story.genre for story in story_list]
    # story_title_list = [story.title for story in story_list]
    #
    stage_tuple_list = []
    for i in range(len(pending_stages)):
         stage_tuple_list.append((pending_stages[i], pending_stage_part_list[i]))
    pending_stage_pk_list = [s.pk for s in pending_stages]
    pending_stage_text_list = [s.text for s in pending_stages]

    pending_storys = Story.objects.filter(status=1).order_by('started_date')

    pending_story_list = list(pending_storys)

    ready_to_publish_story_list = []

    accepted_stages = list(Stage.objects.filter(status=3).order_by('pk'))
    for pending_story in pending_story_list:
        curr_story_stages = []
        for stage in accepted_stages:
            if stage.story == pending_story:
                curr_story_stages.append(stage)
        if len(curr_story_stages) == 5:
            ready_to_publish_story_list.append(pending_story)
    # print(ready_to_publish_story_list)

    context = {
        'username': username,
        'isLogin': True,
        'isAdmin': isAdmin,
        'stage_tuple_list': stage_tuple_list,
        'ready_to_publish_story_list': ready_to_publish_story_list,
        'pending_stage_pk_list': pending_stage_pk_list,
        'pending_stage_text_list': pending_stage_text_list,

        # 'story_list': story_list,
        # 'story_exposition_list': story_author_list,
        # 'story_pk_list': story_pk_list,
        # 'story_genre_list': story_genre_list,
        # 'story_title_list': story_title_list,
        # 'story_tuple_list': story_tuple_list,
    }

    return render(request, 'inprogress.html', context)
@login_required
def to_genre_management(request):
    curr_user = request.user
    isAdmin = curr_user.is_staff
    username = curr_user.username

    # Genre Management Context
    active_genres = Genre.objects.filter(is_active=True).order_by('pk')

    # In-Progress Management Context
    pending_stages = list(Stage.objects.filter(status='1').order_by('pk'))
    pending_stage_part_list = [stage.PART_CHOICES[stage.part-1][1] for stage in pending_stages]
    stage_tuple_list = [(pending_stages[i], pending_stage_part_list[i]) for i in range(len(pending_stages))]
    pending_stage_pk_list = [s.pk for s in pending_stages]
    pending_stage_text_list = [s.text for s in pending_stages]

    pending_storys = Story.objects.filter(status=1).order_by('started_date')
    pending_story_list = list(pending_storys)

    ready_to_publish_story_list = []
    accepted_stages = list(Stage.objects.filter(status=3).order_by('pk'))
    for pending_story in pending_story_list:
        curr_story_stages = [stage for stage in accepted_stages if stage.story == pending_story]
        if len(curr_story_stages) == 5:
            ready_to_publish_story_list.append(pending_story)

    context = {
        'username': username,
        'isLogin': True,
        'isAdmin': isAdmin,
        'active_genres': active_genres,
        'stage_tuple_list': stage_tuple_list,
        'ready_to_publish_story_list': ready_to_publish_story_list,
        'pending_stage_pk_list': pending_stage_pk_list,
        'pending_stage_text_list': pending_stage_text_list,
    }

    return render(request, 'genre_management.html', context)

@login_required
def to_delete_story(request, pk):
    curr_user = request.user
    if not curr_user.is_staff:
        return HttpResponse("Unauthorized", status=401)

    try:
        story = Story.objects.get(pk=pk)
        story.delete()
        messages.success(request, "Story deleted successfully.")
    except Story.DoesNotExist:
        messages.error(request, "Story not found.")

    return redirect('to-read')

@login_required
def to_add_genre(request):
    curr_user = request.user
    isAdmin = curr_user.is_staff
    username = curr_user.username

    if request.method == 'POST':
        curr_user = request.user

        name = request.POST.get('name').title()
        genre_delete_check = request.POST.get('genre_delete_check')
        print(genre_delete_check)
        # TODO: Genre에 이미지 저장할 필드 생성하고 추가할 수 있게 바꿔야함
        new_genre = Genre(
            name=name,
        )
        new_genre.save()

        return redirect('to-genremanagement')

    context = {
        'username': username,
        'isLogin': True,
        'isAdmin': isAdmin,
    }

    return render(request, 'genre_management.html', context)

@login_required
def to_delete_genre(request):
    curr_user = request.user
    isAdmin = curr_user.is_staff
    username = curr_user.username

    if request.method == 'POST':
        curr_user = request.user

        delete_genre_pk_list_str = request.POST.getlist('genre_delete_check')
        delete_genre_pk_list = [int(pk) for pk in delete_genre_pk_list_str]
        print(delete_genre_pk_list)
        for delete_genre_pk in delete_genre_pk_list:
            delete_genre = Genre.objects.get(pk=delete_genre_pk)
            delete_genre.delete()

        return redirect('to-genremanagement')

    context = {
        'username': username,
        'isLogin': True,
        'isAdmin': isAdmin,
    }

    return render(request, 'genre_management.html', context)















