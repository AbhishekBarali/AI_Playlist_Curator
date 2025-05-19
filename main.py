import os
import re
import time
import traceback
import random
from dotenv import load_dotenv
from ytmusicapi import YTMusic
import google.generativeai as genai
from fuzzywuzzy import process, fuzz

# --- CONFIGURATION ---
load_dotenv()
GEMINI_API_KEY = os.getenv("GOOGLE_API_KEY")

# YouTube Music Constants
YTMusic_AUTH_FILE = "headers_auth.json"
SONG_ADD_BATCH_SIZE = 25
MAX_ADD_RETRIES = 3

# --- HUMAN BEHAVIOR MIMICKING CONFIGURATION ---
GENERAL_ACTION_DELAY_MIN_SECONDS = 1.5
GENERAL_ACTION_DELAY_MAX_SECONDS = 4.0
POST_PLAYLIST_CREATE_DELAY_SECONDS = 5
BATCH_ADD_DELAY_MIN_SECONDS = 10
BATCH_ADD_DELAY_MAX_SECONDS = 20
INITIAL_RETRY_DELAY_SECONDS = 10
RETRY_DELAY_MULTIPLIER = 2

# --- FEATURE CONFIGURATION ---
# FETCH_FULL_SONG_DETAILS is now determined by user input
DESCRIPTION_MAX_LENGTH = 250 # For song descriptions if enabled
FETCH_DETAILS_DELAY_MIN_SECONDS = 1.0 # Reduced slightly for faster fetching if user enables it
FETCH_DETAILS_DELAY_MAX_SECONDS = 3.0

# LLM Configuration
LLM_MODEL_NAME = "gemini-2.0-flash"  
LLM_TEMPERATURE = 0.20

# Fuzzy Matching Configuration
FUZZY_MATCH_THRESHOLD = 65

# --- HELPER FUNCTIONS ---

def random_delay(min_sec=GENERAL_ACTION_DELAY_MIN_SECONDS, max_sec=GENERAL_ACTION_DELAY_MAX_SECONDS):
    time.sleep(random.uniform(min_sec, max_sec))

def normalize_text(text: str) -> str:
    if not text: return ""
    text = str(text).lower()
    common_patterns = [
        r"\(official music video\)", r"\(official video\)", r"\(lyric video\)", r"\(lyrics\)",
        r"\[lyrics\]", r"\(audio\)", r"\[audio\]", r"\(hd\)", r"\[hd\]", r"\(hq\)", r"\[hq\]",
        r"\(4k\)", r"\(visualizer\)", r"\(official visualizer\)", r"\(remix\)", r"\(edit\)",
        r"\(radio edit\)", r"\(live\)", r"\[live\]", r"\(acoustic\)", r"\(unplugged\)",
        r"feat\.", r"ft\.", r" explicit", r" clean"
    ]
    for pattern in common_patterns:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)
    text = re.sub(r"[^\w\s'-]", "", text)
    text = text.strip()
    text = re.sub(r"\s+", " ", text)
    return text

def initialize_ytmusic_client() -> YTMusic:
    print("Initializing YouTube Music client...")
    try:
        ytmusic = YTMusic(YTMusic_AUTH_FILE)
        print("YouTube Music client initialized successfully.")
        return ytmusic
    except Exception as e:
        print(f"Error initializing YTMusic: {e}\nEnsure '{YTMusic_AUTH_FILE}' is valid or run 'ytmusicapi oauth'.")
        exit(1)

def initialize_gemini_model() -> genai.GenerativeModel:
    if not GEMINI_API_KEY:
        print("Error: GOOGLE_API_KEY not found in .env file.")
        exit(1)
    print(f"Initializing Gemini AI model ('{LLM_MODEL_NAME}')...")
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        generation_config = genai.types.GenerationConfig(temperature=LLM_TEMPERATURE)
        # Safety settings to be less restrictive if needed, but use with caution
        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        ]
        llm_model = genai.GenerativeModel(
            LLM_MODEL_NAME,
            generation_config=generation_config,
            safety_settings=safety_settings # Apply safety settings
        )
        print("Gemini AI model initialized successfully.")
        return llm_model
    except Exception as e:
        print(f"Error initializing Gemini AI: {e}")
        traceback.print_exc()
        exit(1)

def get_user_playlist_choice(ytmusic_client: YTMusic) -> tuple[str, str]:
    print("\nFetching your YouTube Music playlists...")
    random_delay(0.5, 1.5)
    try:
        library_playlists = ytmusic_client.get_library_playlists(limit=200)
        if not library_playlists:
            print("No playlists found in your library.")
            exit(1)
        print("\nYour Playlists:")
        for i, pl in enumerate(library_playlists): print(f"{i + 1}. {pl['title']}")
        while True:
            try:
                choice = int(input("\nEnter the number of the playlist to organize: ")) - 1
                if 0 <= choice < len(library_playlists):
                    pl_id, pl_title = library_playlists[choice]['playlistId'], library_playlists[choice]['title']
                    print(f"\nYou selected playlist: '{pl_title}'")
                    return pl_id, pl_title
                else: print(f"Invalid number. Please enter 1-{len(library_playlists)}.")
            except ValueError: print("Invalid input. Please enter a number.")
    except Exception as e:
        print(f"Error fetching/processing playlists: {e}"); traceback.print_exc(); exit(1)

def get_fetch_details_preference() -> bool:
    """Asks the user if they want to fetch detailed song descriptions."""
    print("\n--- Song Detail Fetching ---")
    print("Would you like to fetch detailed descriptions for each song (from YouTube)?")
    print("This can provide more context to the AI but will significantly increase processing time and API calls.")
    while True:
        choice = input("Fetch full song details? (yes/no)(Enabled mode only reccomended using twice a day at max) : ").strip().lower()
        if choice in ['yes', 'y']:
            print("Fetching full song details ENABLED.")
            return True
        elif choice in ['no', 'n']:
            print("Fetching full song details DISABLED.")
            return False
        else:
            print("Invalid input. Please enter 'yes' or 'no'.")

def get_detailed_playlist_criteria() -> dict:
    """Gets detailed criteria for the new playlist from the user."""
    print("\n--- New Playlist Details ---")
    criteria = {}
    while not (title := input("Enter the title for your new sub-playlist: ").strip()):
        print("Playlist title cannot be empty.")
    criteria['title'] = title

    criteria['description'] = input("Enter a detailed description for the playlist (e.g., 'Upbeat electronic for coding', 'Melancholic acoustic for a rainy day') (optional, press Enter to skip): ").strip()
    criteria['genres'] = input("List desired genre(s), comma-separated (e.g., 'synthwave, retrowave, electronic') (optional): ").strip().lower()
    criteria['artists'] = input("List preferred artist(s), comma-separated (e.g., 'Wanye, Yuno Miles') (optional): ").strip()
    criteria['moods'] = input("Describe the desired mood(s)/vibe(s), comma-separated (e.g., 'energetic, nostalgic, focused') (optional): ").strip().lower()
    criteria['keywords'] = input("Any other keywords, comma-separated (e.g., '80s, instrumental, driving beat,beating people') (optional): ").strip().lower()

    print("\nPlaylist criteria captured.")
    return criteria

def fetch_playlist_songs(
    ytmusic_client: YTMusic,
    source_playlist_id: str,
    source_playlist_title: str,
    fetch_full_details_flag: bool
) -> tuple[list[str], dict]:
    print(f"\nFetching songs from playlist '{source_playlist_title}'...")
    if fetch_full_details_flag:
        print("INFO: Fetching full song details is ON (includes descriptions - can be slow, high API usage).")
    else:
        print("Note: Fetching limited song details (Title, Artist, Album if available). Descriptions will NOT be fetched.")
    random_delay(1.0, 2.5)
    try:
        playlist_details = ytmusic_client.get_playlist(playlistId=source_playlist_id, limit=None)
        source_songs_raw = playlist_details.get("tracks", [])
        if not source_songs_raw: print(f"No songs found in '{source_playlist_title}'."); exit(1)

        song_data_for_llm, source_song_data_map = [], {}
        total_songs = len(source_songs_raw)
        print(f"Processing {total_songs} raw song entries...")

        for i, song_raw in enumerate(source_songs_raw):
            if not (song_raw and song_raw.get("videoId")): continue
            title, video_id = song_raw.get("title", "Unknown Title"), song_raw.get("videoId")
            artist_name = "Unknown Artist"
            if artists := song_raw.get('artists'):
                artist_names = [a['name'] for a in artists if a.get('name')]
                if artist_names: artist_name = " & ".join(artist_names)
                elif artists and artists[0].get('name'): artist_name = artists[0]['name']

            album_name = None
            if album_info := song_raw.get('album'):
                if isinstance(album_info, dict): album_name = album_info.get('name')

            llm_entry_parts = [f"Title: {title}", f"Artist: {artist_name}"]
            if album_name: llm_entry_parts.append(f"Album: {album_name}")
            llm_output_identifier = f"{title} by {artist_name}"

            song_metadata_for_map = {
                "videoId": video_id, "original_title": title, "original_artist": artist_name,
                "original_album": album_name, "llm_identifier": llm_output_identifier
            }

            if fetch_full_details_flag:
                print(f"  Fetching details for '{title}' ({i+1}/{total_songs})...")
                random_delay(FETCH_DETAILS_DELAY_MIN_SECONDS, FETCH_DETAILS_DELAY_MAX_SECONDS)
                try:
                    song_details_yt = ytmusic_client.get_song(videoId=video_id)
                    description = song_details_yt.get('description', '')
                    if description:
                        # Get first line or first significant part of description for brevity
                        first_line_desc = description.split('\n')[0].strip()
                        normalized_desc = normalize_text(first_line_desc)
                        truncated_desc = normalized_desc[:DESCRIPTION_MAX_LENGTH]
                        if truncated_desc:
                            llm_entry_parts.append(f"Description: {truncated_desc}")
                            song_metadata_for_map["description"] = truncated_desc
                except Exception as e_detail:
                    print(f"    Warning: Could not fetch/process details for song ID {video_id} ('{title}'): {e_detail}")
                    # Continue without description if fetching fails

            current_llm_entry_string = "\n".join(llm_entry_parts)
            song_data_for_llm.append(current_llm_entry_string)
            source_song_data_map[current_llm_entry_string] = song_metadata_for_map

            if (i + 1) % 20 == 0 and total_songs > 20: print(f"  Processed {i+1}/{total_songs} songs...")

        if not song_data_for_llm: print("No processable songs found."); exit(1)
        print(f"Successfully processed {len(song_data_for_llm)} songs for LLM input.")
        return song_data_for_llm, source_song_data_map
    except Exception as e:
        print(f"Error fetching/processing songs: {e}"); traceback.print_exc(); exit(1)

def get_ai_song_suggestions(
    llm_model: genai.GenerativeModel,
    playlist_criteria: dict,
    song_data_for_llm: list[str]
) -> list[str]:
    new_playlist_title = playlist_criteria['title']
    print(f"\nAsking AI to select songs for the new playlist: '{new_playlist_title}' based on detailed criteria...")
    print("This may take a moment...")
    random_delay(1,3)

    if not song_data_for_llm:
        print("No song data provided to LLM."); return []

    songs_list_for_prompt = "\n---\n".join(song_data_for_llm)
    has_album_data = any("Album:" in entry for entry in song_data_for_llm)
    has_description_data = any("Description:" in entry for entry in song_data_for_llm)

    criteria_prompt_parts = [f"The user wants to create a new playlist titled: \"{new_playlist_title}\"."]
    if desc := playlist_criteria.get('description'):
        criteria_prompt_parts.append(f"Playlist Description: {desc}")
    if genres := playlist_criteria.get('genres'):
        criteria_prompt_parts.append(f"Desired Genre(s): {genres}")
    if artists := playlist_criteria.get('artists'):
        criteria_prompt_parts.append(f"Preferred Artist(s) (consider these strongly if their songs appear in the list): {artists}")
    if moods := playlist_criteria.get('moods'):
        criteria_prompt_parts.append(f"Desired Mood(s)/Vibe(s): {moods}")
    if keywords := playlist_criteria.get('keywords'):
        criteria_prompt_parts.append(f"Other Keywords: {keywords}")

    criteria_summary_prompt = "\n".join(criteria_prompt_parts)

    prompt_intro = f"""You are an expert music curator AI.
{criteria_summary_prompt}

Your task is to carefully review the "Available songs" list below. Each song entry is separated by "---".
Each song entry includes Title and Artist. """

    available_info_parts = ["Title", "Artist"]
    if has_album_data: available_info_parts.append("Album")
    if has_description_data: available_info_parts.append("Description")

    available_info_str = " and ".join(filter(None, [", ".join(available_info_parts[:-1]), available_info_parts[-1]])) if len(available_info_parts) > 1 else available_info_parts[0]
    
    prompt_intro += f"It may also include {'an Album title' if has_album_data else ''}{' and a song Description' if has_description_data and has_album_data else ''}{'a song Description' if has_description_data and not has_album_data else ''}. "
    prompt_intro += f"Use ALL available information ({available_info_str}) for each song in the list to make your choices.\n"


    prompt_intro += f"""
Critically evaluate how well each song from the "Available songs" list aligns with the user's detailed playlist criteria.
Consider things like:
- Does the song's Artist typically align with the requested genres or preferred artists? (If preferred artists are listed, prioritize their songs if they fit the overall theme).
- Does the song's Title (and Album Title{', and Description' if has_description_data else ''}, if available) evoke the requested mood, theme, or keywords?
- Even if an artist is preferred, ensure the specific song fits the overall request.

Select ONLY the songs from the "Available songs" list that genuinely and strongly fit the user's detailed request.
If a song is a weak match, ambiguous, or you cannot confidently determine its fit from its {available_info_str} against the user's criteria, DO NOT include it.
It is better to be conservative and select fewer, highly relevant songs.
Do NOT use any external knowledge about songs beyond what is provided in the "Available songs" list. Your selection must be based on the given data for each song.
"""

    prompt_critical_instructions = f"""
CRITICAL INSTRUCTIONS FOR OUTPUT FORMAT:
1.  Output ONLY the selected songs.
2.  For EACH selected song, output its "Title by Artist" string on a new line.
    For example: "Song Title by Artist Name"
3.  This "Title by Artist" string MUST EXACTLY MATCH the title and artist as they were provided in the input for that specific song (this forms the 'llm_identifier' for matching).
4.  Do NOT include "Description:", "Album:", "---", any numbering, bullet points, introductory text, concluding text, or ANY other characters or commentary.
    Your response should be ONLY the list of "Title by Artist" strings, each on its own line.

Available songs:
{songs_list_for_prompt}

Selected songs for "{new_playlist_title}" based on the detailed criteria:
"""
    full_prompt = prompt_intro + prompt_critical_instructions

    try:
        # print(f"DEBUG: Full prompt to LLM:\n{full_prompt[:2000]}...\n") # For debugging long prompts
        response = llm_model.generate_content(full_prompt)

        if not response.parts:
            print("\nAI response was empty or blocked. This might be due to safety filters or an issue with the prompt/model.")
            if hasattr(response, 'prompt_feedback') and response.prompt_feedback:
                print(f"Prompt Feedback: {response.prompt_feedback}")
            # Attempt to print candidate if available and blocked
            if hasattr(response, 'candidates') and response.candidates:
                 for candidate_idx, candidate in enumerate(response.candidates):
                    if hasattr(candidate, 'finish_reason') and candidate.finish_reason != 'STOP':
                        print(f"  Candidate {candidate_idx+1} Blocked. Reason: {candidate.finish_reason}")
                        if hasattr(candidate, 'safety_ratings'):
                             print(f"  Safety Ratings: {candidate.safety_ratings}")
            return []

        ai_output = response.text.strip()
        suggested_llm_identifiers = [line.strip() for line in ai_output.split("\n") if line.strip()]

        if not suggested_llm_identifiers:
            print(f"\nAI did not suggest any songs or the output was empty/malformed.\nLLM Raw Output:\n---\n{ai_output}\n---")
            return []
        print(f"\nAI suggested {len(suggested_llm_identifiers)} songs based on detailed criteria:")
        for item in suggested_llm_identifiers: print(f"  - '{item}'")
        return suggested_llm_identifiers
    except Exception as e:
        print(f"An error during AI song suggestion: {e}")
        if 'response' in locals() and hasattr(response, 'text'): print(f"LLM Raw Output:\n---\n{response.text}\n---")
        elif 'response' in locals() and hasattr(response, 'prompt_feedback'): print(f"LLM Prompt Feedback: {response.prompt_feedback}")
        else: print("LLM Raw Output/Feedback not available.")
        traceback.print_exc()
        return []

def match_songs_to_video_ids(
    suggested_llm_identifiers: list[str], source_song_data_map: dict
) -> list[str]:
    print("\nMatching AI's suggestions to original playlist data...")
    random_delay(0.5, 1.5)
    video_ids_to_add, unique_matched_ids = [], set()
    if not suggested_llm_identifiers: print("No AI suggestions to match."); return []

    choices_for_fuzzy = [(normalize_text(data['llm_identifier']), key) # key here is current_llm_entry_string
                         for key, data in source_song_data_map.items() if data.get('llm_identifier')]
    if not choices_for_fuzzy:
        print("Error: No 'llm_identifier' in source_song_data_map values. Cannot match."); return []

    # Create a lookup from normalized llm_identifier to the original source_song_data_map key
    norm_id_to_source_key_map = {norm_id: src_key for norm_id, src_key in choices_for_fuzzy}


    for ai_suggestion in suggested_llm_identifiers:
        norm_ai_suggestion = normalize_text(ai_suggestion)
        if not norm_ai_suggestion:
            print(f"  Skipping empty/normalized-away AI suggestion: '{ai_suggestion}'"); continue

        # Fuzzy match against the normalized 'llm_identifier' strings
        match_result = process.extractOne(
            norm_ai_suggestion,
            [choice[0] for choice in choices_for_fuzzy], # Match against normalized llm_identifiers
            scorer=fuzz.WRatio,
            score_cutoff=FUZZY_MATCH_THRESHOLD
        )

        if match_result:
            matched_norm_llm_id_str, score = match_result
            # Find the original source_song_data_map key using the matched normalized llm_identifier string
            best_match_source_key = norm_id_to_source_key_map.get(matched_norm_llm_id_str)

            if best_match_source_key:
                data = source_song_data_map[best_match_source_key]
                vid, title, artist = data['videoId'], data['original_title'], data['original_artist']
                if vid not in unique_matched_ids:
                    video_ids_to_add.append(vid); unique_matched_ids.add(vid)
                    print(f"  Matched (Score: {score}%): AI '{ai_suggestion}' -> '{title} by {artist}' (ID: {vid})")
                else:
                    print(f"  Info: Song '{title} by {artist}' already matched for AI suggestion '{ai_suggestion}'.")
            else:
                print(f"  Warning: Internal mismatch after fuzzy matching for AI suggestion '{ai_suggestion}'. Could not map '{matched_norm_llm_id_str}' back to a source key.")
        else:
            # Attempt direct key lookup as a fallback if the AI's output exactly matches an original llm_identifier
            # (This is less likely given fuzzy matching is primary, but good for perfect matches not caught by fuzzy due to normalization nuances)
            direct_match_key = next((key for key, data_val in source_song_data_map.items() if normalize_text(data_val.get('llm_identifier', '')) == norm_ai_suggestion), None)
            if direct_match_key:
                data = source_song_data_map[direct_match_key]
                vid, title, artist = data['videoId'], data['original_title'], data['original_artist']
                if vid not in unique_matched_ids:
                    video_ids_to_add.append(vid); unique_matched_ids.add(vid)
                    print(f"  Matched (Direct): AI '{ai_suggestion}' -> '{title} by {artist}' (ID: {vid})")
                else:
                    print(f"  Info: Song '{title} by {artist}' already matched (direct) for AI suggestion '{ai_suggestion}'.")
            else:
                 print(f"  Warning: Could not confidently match AI suggestion: '{ai_suggestion}' (Normalized: '{norm_ai_suggestion}') using fuzzy matching or direct lookup.")


    if not video_ids_to_add: print("\nNo songs successfully matched from AI suggestions.")
    else: print(f"\nSuccessfully matched {len(video_ids_to_add)} unique songs.")
    return video_ids_to_add

def create_playlist_and_add_songs(
    ytmusic_client: YTMusic, new_playlist_title: str, source_playlist_title: str,
    video_ids_to_add: list[str], playlist_criteria: dict
) -> None:
    if not video_ids_to_add:
        print("\nNo songs to add. Playlist creation aborted.")
        return

    print(f"\nPreparing to create playlist '{new_playlist_title}' with {len(video_ids_to_add)} songs.")
    if input("Proceed? (yes/no): ").strip().lower() != "yes":
        print("Playlist creation aborted.")
        return

    desc_parts = [f"AI-curated: '{new_playlist_title}' from '{source_playlist_title}'."]
    if critères_desc := playlist_criteria.get('description'):
        desc_parts.append(f"User defined as: \"{critères_desc[:200]}{'...' if len(critères_desc) > 200 else ''}\"")
    if genres := playlist_criteria.get('genres'):
        desc_parts.append(f"Genres: {genres}.")
    if moods := playlist_criteria.get('moods'):
        desc_parts.append(f"Moods: {moods}.")
    final_description = " ".join(desc_parts)[:5000] # YT Music description limit is 5000

    print(f"\nCreating playlist '{new_playlist_title}'...")
    random_delay(1, 2)
    new_playlist_id = None
    try:
        new_playlist_id = ytmusic_client.create_playlist(
            title=new_playlist_title, description=final_description
        )
        print(f"Playlist '{new_playlist_title}' (ID: {new_playlist_id}) created.")
        print(f"Waiting {POST_PLAYLIST_CREATE_DELAY_SECONDS}s for server sync...")
        time.sleep(POST_PLAYLIST_CREATE_DELAY_SECONDS)
    except Exception as e:
        print(f"Error creating playlist: {e}")
        traceback.print_exc()
        return

    print(f"\nAdding {len(video_ids_to_add)} songs to '{new_playlist_title}' in batches...")
    added_count = 0
    globally_failed_or_unconfirmed_ids = []

    for i in range(0, len(video_ids_to_add), SONG_ADD_BATCH_SIZE):
        current_batch_ids_to_attempt = video_ids_to_add[i : i + SONG_ADD_BATCH_SIZE]
        batch_num = (i // SONG_ADD_BATCH_SIZE) + 1
        print(f"\n  Processing batch {batch_num} ({len(current_batch_ids_to_attempt)} songs)...")

        if i > 0:
            random_delay(BATCH_ADD_DELAY_MIN_SECONDS, BATCH_ADD_DELAY_MAX_SECONDS)

        ids_in_batch_still_to_confirm = list(current_batch_ids_to_attempt)
        # batch_fully_processed_or_max_retries = False # Removed, logic simplified

        for attempt_num in range(MAX_ADD_RETRIES):
            if not ids_in_batch_still_to_confirm:
                break

            if attempt_num > 0:
                current_retry_delay = INITIAL_RETRY_DELAY_SECONDS * (RETRY_DELAY_MULTIPLIER ** (attempt_num -1))
                print(f"    Retrying {len(ids_in_batch_still_to_confirm)} unconfirmed song(s) in batch {batch_num} (Attempt {attempt_num + 1}/{MAX_ADD_RETRIES}) in {current_retry_delay:.1f}s...")
                time.sleep(current_retry_delay)
            else:
                 print(f"    Attempting to add {len(ids_in_batch_still_to_confirm)} song(s) (Attempt {attempt_num + 1}/{MAX_ADD_RETRIES})")

            ids_confirmed_this_api_call = []

            try:
                result = ytmusic_client.add_playlist_items(playlistId=new_playlist_id, videoIds=ids_in_batch_still_to_confirm, duplicates=False)
                # print(f"DEBUG: Batch {batch_num}, Attempt {attempt_num + 1} API Result: {result}")

                if isinstance(result, dict):
                    if "actionResults" in result and isinstance(result["actionResults"], list) and result["actionResults"]:
                        temp_ids_confirmed_from_action_results = []
                        for ar_idx, action_result_item in enumerate(result["actionResults"]):
                            if isinstance(action_result_item, dict) and action_result_item.get("status") == "STATUS_SUCCEEDED":
                                video_id_from_ar = action_result_item.get("item", {}).get("videoId")
                                if not video_id_from_ar and ar_idx < len(ids_in_batch_still_to_confirm):
                                    video_id_from_ar = ids_in_batch_still_to_confirm[ar_idx]
                                if video_id_from_ar:
                                    temp_ids_confirmed_from_action_results.append(video_id_from_ar)
                        
                        if temp_ids_confirmed_from_action_results:
                             print(f"    Batch {batch_num}, Attempt {attempt_num + 1}: {len(temp_ids_confirmed_from_action_results)}/{len(ids_in_batch_still_to_confirm)} songs confirmed via actionResults.")
                             ids_confirmed_this_api_call.extend(temp_ids_confirmed_from_action_results)
                        # If actionResults is present but empty, or no successes, it implies failure for all *in this attempt*
                        # For other cases, we rely on the general status or actions.

                    elif result.get('status') == 'SUCCEEDED':
                        print(f"    Batch {batch_num}, Attempt {attempt_num + 1}: API overall status SUCCEEDED. Assuming all {len(ids_in_batch_still_to_confirm)} attempted songs in this call were added.")
                        ids_confirmed_this_api_call.extend(list(ids_in_batch_still_to_confirm))

                    elif 'actions' in result and isinstance(result['actions'], list) and result['actions']:
                        if any(action.get('addToPlaylistFeedback') == 'SUCCESS' for action in result['actions'] if isinstance(action,dict)):
                            print(f"    Batch {batch_num}, Attempt {attempt_num + 1}: Processed with 'addToPlaylistFeedback': SUCCESS. Assuming all {len(ids_in_batch_still_to_confirm)} attempted songs added.")
                            ids_confirmed_this_api_call.extend(list(ids_in_batch_still_to_confirm))
                        else:
                            print(f"    Batch {batch_num}, Attempt {attempt_num + 1}: 'actions' key present but no 'SUCCESS' feedback. Result: {result}")
                    else:
                        print(f"    Batch {batch_num}, Attempt {attempt_num + 1}: API response lacks clear success indicators. Result: {result}")
                else:
                    print(f"    Batch {batch_num}, Attempt {attempt_num + 1}: Unexpected API response format (not a dict). Result: {result}")

                if ids_confirmed_this_api_call:
                    newly_confirmed_count = 0
                    temp_still_to_confirm = list(ids_in_batch_still_to_confirm) # Iterate over a copy
                    for vid_id in ids_confirmed_this_api_call:
                        if vid_id in temp_still_to_confirm:
                            ids_in_batch_still_to_confirm.remove(vid_id) # Remove from original list
                            added_count += 1
                            newly_confirmed_count +=1
                    if newly_confirmed_count > 0:
                        print(f"    Batch {batch_num}: {newly_confirmed_count} song(s) newly confirmed this attempt.")

                if not ids_in_batch_still_to_confirm:
                    print(f"    Batch {batch_num}: All songs successfully processed and confirmed.")
                    break

            except Exception as e_add:
                print(f"    Error during API call for batch {batch_num} (Attempt {attempt_num + 1}/{MAX_ADD_RETRIES}): {e_add}")

            if attempt_num == MAX_ADD_RETRIES - 1 and ids_in_batch_still_to_confirm:
                 print(f"    Batch {batch_num}: After {MAX_ADD_RETRIES} attempts, {len(ids_in_batch_still_to_confirm)} song(s) remain unconfirmed.")

        for unconfirmed_vid in ids_in_batch_still_to_confirm:
            if unconfirmed_vid not in globally_failed_or_unconfirmed_ids:
                globally_failed_or_unconfirmed_ids.append(unconfirmed_vid)

    print("\n--- Song Addition Summary ---")
    if added_count > 0:
        print(f"Successfully confirmed addition of {added_count} song(s) to '{new_playlist_title}'.")
        if len(video_ids_to_add) - added_count > 0 :
             print(f"Attempted to add {len(video_ids_to_add)} songs in total.")
        print(f"View playlist: https://music.youtube.com/playlist?list={new_playlist_id}")
    else:
        print(f"No songs were confirmed as added to '{new_playlist_title}' after all attempts.")

    if globally_failed_or_unconfirmed_ids:
        print(f"\nWarning: {len(globally_failed_or_unconfirmed_ids)} video ID(s) could not be confirmed as added after all retries (These might have been added (check your youtube account for new playlist) but the API response was inconclusive, or they failed):")
        for vid_idx, vid in enumerate(globally_failed_or_unconfirmed_ids):
            print(f"  - {vid}")
            if vid_idx >= 9 and len(globally_failed_or_unconfirmed_ids) > 10:
                print(f"  ... and {len(globally_failed_or_unconfirmed_ids) - (vid_idx + 1)} more.")
                break
    elif added_count == len(video_ids_to_add) and video_ids_to_add:
        print("All requested songs were confirmed as added successfully!")

    print("--- End of Summary ---")


# --- MAIN EXECUTION ---
def main():
    print("Starting AI Playlist Curator...")
    ytmusic = initialize_ytmusic_client()
    llm_model = initialize_gemini_model()
    random_delay()

    fetch_details_user_preference = get_fetch_details_preference()
    random_delay()

    source_playlist_id, source_playlist_title = get_user_playlist_choice(ytmusic)
    random_delay()

    song_data_for_llm, source_song_data_map = fetch_playlist_songs(
        ytmusic, source_playlist_id, source_playlist_title, fetch_details_user_preference
    )
    if not song_data_for_llm: print("No song data to process. Exiting."); exit(1)
    random_delay()

    playlist_criteria = get_detailed_playlist_criteria()
    random_delay()

    suggested_llm_ids = get_ai_song_suggestions(
        llm_model, playlist_criteria, song_data_for_llm
    )
    if not suggested_llm_ids: print("AI gave no suggestions. Exiting."); exit(1)
    random_delay()

    video_ids_for_playlist = match_songs_to_video_ids(
        suggested_llm_ids, source_song_data_map
    )
    if not video_ids_for_playlist: print("No songs matched from AI. Exiting."); exit(1)
    random_delay()

    create_playlist_and_add_songs(
        ytmusic, playlist_criteria['title'], source_playlist_title,
        video_ids_for_playlist, playlist_criteria
    )

    print("\n✅ Playlist creation process finished!")

if __name__ == "__main__":
    main()
