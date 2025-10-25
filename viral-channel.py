import streamlit as st
import requests
from datetime import datetime, timedelta

# YouTube API Key
API_KEY = "AIzaSyDJcigV37FRMhkO73M97OUm85tb82y6HM0"  # Enter your API Key here
YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
YOUTUBE_VIDEO_URL = "https://www.googleapis.com/youtube/v3/videos"
YOUTUBE_CHANNEL_URL = "https://www.googleapis.com/youtube/v3/channels"

# Streamlit App Title
st.title("YouTube Channel Discovery Tool")

# Input Fields
days = st.number_input("Enter Days to Search (1-30):", min_value=1, max_value=30, value=7)
min_subs = st.number_input("Enter Minimum Subscriber Count:", min_value=0, max_value=100000, value=1000)
max_subs = st.number_input("Enter Maximum Subscriber Count:", min_value=0, max_value=100000, value=5000)

# Country list for dropdown (example, can be expanded as needed)
countries = ['India', 'United States', 'United Kingdom', 'Australia', 'Canada', 'Germany', 'Japan', 'Brazil']
selected_country = st.selectbox("Select a Country", countries)

# Time Period Dropdown (7 days, 14 days, 28 days)
time_period = st.selectbox("Select Time Period", ["7 Days", "14 Days", "28 Days"])

# Fetch Data Button
if st.button("Fetch Data"):
    if not selected_country:
        st.warning("Please select a country and provide a topic to search.")
    else:
        try:
            # Set date range based on selected time period
            if time_period == "7 Days":
                start_date = (datetime.utcnow() - timedelta(days=7)).isoformat("T") + "Z"
            elif time_period == "14 Days":
                start_date = (datetime.utcnow() - timedelta(days=14)).isoformat("T") + "Z"
            else:
                start_date = (datetime.utcnow() - timedelta(days=28)).isoformat("T") + "Z"
            
            all_results = []

            # Define search parameters for videos based on the topic
            search_params = {
                "part": "snippet",
                "q": selected_country,  # Search for videos related to the selected country
                "type": "video",
                "publishedAfter": start_date,  # Filter by the selected time period
                "maxResults": 10,  # Get up to 10 videos
                "key": API_KEY,
            }

            # Fetch video data based on country and time period
            response = requests.get(YOUTUBE_SEARCH_URL, params=search_params)
            data = response.json()

            if "items" not in data or not data["items"]:
                st.warning(f"No videos found for country: {selected_country} in the last {time_period}.")
            else:
                video_ids = [video["id"]["videoId"] for video in data["items"]]
                channel_ids = [video["snippet"]["channelId"] for video in data["items"]]

                # Fetch video statistics
                stats_params = {"part": "statistics", "id": ",".join(video_ids), "key": API_KEY}
                stats_response = requests.get(YOUTUBE_VIDEO_URL, params=stats_params)
                stats_data = stats_response.json()

                # Fetch channel statistics
                channel_params = {"part": "statistics,snippet", "id": ",".join(channel_ids), "key": API_KEY}
                channel_response = requests.get(YOUTUBE_CHANNEL_URL, params=channel_params)
                channel_data = channel_response.json()

                # Check if we have valid statistics and channels data
                if "items" not in stats_data or not stats_data["items"] or "items" not in channel_data or not channel_data["items"]:
                    st.warning("Failed to fetch video or channel statistics.")
                else:
                    stats = stats_data["items"]
                    channels = channel_data["items"]

                    # Process and filter results for videos
                    for video, stat, channel in zip(data["items"], stats, channels):
                        title = video["snippet"].get("title", "N/A")
                        description = video["snippet"].get("description", "")[:200]  # Limit description to 200 chars
                        video_url = f"https://www.youtube.com/watch?v={video['id']['videoId']}"
                        views = int(stat["statistics"].get("viewCount", 0))
                        subs = int(channel["statistics"].get("subscriberCount", 0))
                        country = channel["snippet"].get("country", "N/A")  # Country (if available)
                        channel_category = channel["snippet"].get("categoryId", "N/A")  # Niche/Category
                        
                        # Channel creation date and age
                        creation_date = channel["snippet"].get("publishedAt", "1970-01-01T00:00:00Z")
                        creation_date = datetime.strptime(creation_date, "%Y-%m-%dT%H:%M:%SZ")
                        channel_age = (datetime.utcnow() - creation_date).days

                        # Apply filters for channels with 1k-5k subscribers
                        if min_subs <= subs <= max_subs:
                            all_results.append({
                                "Channel Name": channel["snippet"]["channelTitle"],
                                "Channel URL": f"https://www.youtube.com/channel/{channel['id']}",
                                "Subscribers": subs,
                                "Age (Days)": channel_age,
                                "Country": country,
                                "Niche": channel_category,
                            })

            # Display results
            if all_results:
                st.success(f"Found {len(all_results)} channels matching the selected filters!")
                for result in all_results:
                    st.markdown(f"### {result['Channel Name']}")
                    st.markdown(f"**Subscribers:** {result['Subscribers']}")
                    st.markdown(f"**Age:** {result['Age (Days)']} days")
                    st.markdown(f"**Country:** {result['Country']}")
                    st.markdown(f"**Niche:** {result['Niche']}")
                    st.markdown(f"[Visit Channel]({result['Channel URL']})")
                    st.write("---")
            else:
                st.warning("No channels found matching the selected filters.")

        except Exception as e:
            st.error(f"An error occurred: {e}")
