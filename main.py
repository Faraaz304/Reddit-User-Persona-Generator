import os
import requests
from bs4 import BeautifulSoup
import time
import re
import google.generativeai as genai
from dotenv import load_dotenv

# --- SCRIPT SETUP ---
# Load environment variables from a .env file
load_dotenv()

# --- REDDIT SCRAPING (NO API KEY NEEDED) ---

def scrape_reddit_user_no_api(username, pages=3):
    """Scrapes a user's public comments and posts from old.reddit.com without an API key."""
    print(f"\nScraping public data for user: {username} from old.reddit.com...")
    base_url = f"https://old.reddit.com/user/{username}"
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    formatted_texts_with_source = []

    for content_type in ["submitted", "comments"]:
        print(f"Fetching {content_type}...")
        after = None
        for i in range(pages):
            url = f"{base_url}/{content_type}/?count={i * 25}&after={after if after else ''}"
            try:
                response = requests.get(url, headers=headers, timeout=10)
                response.raise_for_status()
            except requests.exceptions.RequestException as e:
                print(f"Error fetching URL {url}: {e}")
                break

            soup = BeautifulSoup(response.text, 'html.parser')
            
            if i == 0 and not soup.select_one('div.content'):
                 print(f"Error: User '{username}' not found or profile is private/banned.")
                 return None

            entries = soup.select('div.thing')
            if not entries:
                if i == 0: print(f"No {content_type} found for this user.")
                break

            for entry in entries:
                text_element = entry.select_one('div.md')
                if text_element:
                    text = text_element.get_text(separator='\n', strip=True)
                    permalink_element = entry.select_one('a.bylink')
                    if permalink_element:
                        source_url = permalink_element['href']
                        formatted_texts_with_source.append(f"[Source: {source_url}]\n{text}\n")

            next_button = soup.select_one('span.next-button a')
            if next_button and 'href' in next_button.attrs:
                after_match = re.search(r'after=([^&]+)', next_button['href'])
                if after_match:
                    after = after_match.group(1)
                    time.sleep(2)
                else: break
            else: break

    if not formatted_texts_with_source:
        print(f"No public content found for user '{username}'.")
        return None
    
    print(f"Successfully scraped {len(formatted_texts_with_source)} items.")
    return "\n---\n".join(formatted_texts_with_source)

# --- PERSONA GENERATION (USING GEMINI API) ---

def generate_persona_gemini(user_data, api_key):
    """Uses the Gemini API to generate a detailed, cited user persona."""
    print("\nAnalyzing data with Google Gemini API...")
    
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
    except Exception as e:
        print(f"❌ Error configuring the Gemini API. Is your API key in the .env file valid? Error: {e}")
        return None

    prompt = f"""
    You are an expert user profiler. Based on the following Reddit posts and comments,
    create a detailed user persona.

    **Instructions:**
    1.  Create sections for: Bio, Demographics (Inferred), Interests & Hobbies, and Personality Traits.
    2.  **For every point you make, you MUST cite the [Source: ...] URL that gave you the information.**
    3.  If you cannot find information for a section, state "Insufficient information from provided data."
    4.  Be objective and only use the data provided below.

    **User Data:**
    {user_data}
    """

    try:
        response = model.generate_content(prompt)
        if not response.parts:
             print("❌ Gemini API returned an empty response. This might be due to a content safety filter. Try a different user.")
             return None
        return response.text
    except Exception as e:
        print(f"❌ An error occurred while communicating with the Gemini API: {e}")
        return None

# --- UTILITY FUNCTIONS ---

def get_username_from_url(url):
    """Extracts the username from a Reddit profile URL."""
    match = re.search(r'(?:/u/|/user/)([^/]+)', url)
    if match:
        return match.group(1).strip('/')
    else:
        raise ValueError("Invalid Reddit user URL format. Expected format: https://www.reddit.com/user/username/")

def save_persona_to_file(username, persona_text):
    """Saves the generated persona to a text file."""
    filename = f"persona_gemini_{username}.txt"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(persona_text)
    print(f"\n✅ Success! Persona saved to {filename}")

# --- MAIN EXECUTION ---

def main():
    """Main function to orchestrate the script."""
    # 1. Get the Gemini API Key from the .env file
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    
    # Check if the key was found
    if not gemini_api_key:
        print("❌ Error: GEMINI_API_KEY not found in your .env file.")
        print("Please create a .env file in the same directory with the line:")
        print('GEMINI_API_KEY="your_actual_api_key_here"')
        return

    try:
        # 2. Get the Reddit URL from the user
        user_url = input("➡️ Please enter the full PUBLIC Reddit user profile URL: ").strip()
        if not user_url:
            print("❌ URL cannot be empty.")
            return

        # 3. Scrape Reddit using the URL (no key needed)
        username = get_username_from_url(user_url)
        user_data = scrape_reddit_user_no_api(username)
        if not user_data:
            return

        # 4. Analyze content using the Gemini API key
        persona = generate_persona_gemini(user_data, gemini_api_key)
        if not persona:
            print("Persona generation failed.")
            return

        # 5. Save the result
        save_persona_to_file(username, persona)

    except ValueError as e:
        print(f"❌ Error: {e}")
    except KeyboardInterrupt:
        print("\nProcess interrupted by user. Exiting.")
    except Exception as e:
        print(f"❌ An unexpected error occurred: {e}")

if __name__ == "__main__":
    main()