import streamlit as st
import requests
from datetime import datetime, timedelta

# YouTube API Configuration
API_KEY = "AIzaSyDJcigV37FRMhkO73M97OUm85tb82y6HM0"
YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
YOUTUBE_VIDEO_URL = "https://www.googleapis.com/youtube/v3/videos"
YOUTUBE_CHANNEL_URL = "https://www.googleapis.com/youtube/v3/channels"

# Page Configuration
st.set_page_config(page_title="YouTube Research Tool", page_icon="🔍", layout="wide")
st.title("🔍 YouTube Channel Research Tool")
st.markdown("**Discover new YouTube channels based on your custom criteria**")

# ============================================
# SIDEBAR - INPUT PARAMETERS
# ============================================
st.sidebar.header("⚙️ Search Configuration")

# 1. KEYWORD INPUT (User-Defined)
st.sidebar.subheader("1️⃣ Keywords")
keywords_input = st.sidebar.text_area(
    "Enter Keywords (one per line):",
    value="Reddit Stories\nCheating Stories\nRelationship Advice",
    height=150,
    help="Enter one keyword per line to search for relevant videos"
)
keywords = [k.strip() for k in keywords_input.split('\n') if k.strip()]

# 2. TIME RANGE FILTER (User-Defined)
st.sidebar.subheader("2️⃣ Video Upload Time")
time_range = st.sidebar.selectbox(
    "Videos uploaded within:",
    ["Last 24 Hours", "Last 7 Days", "Last 30 Days", "Last 3 Months", 
     "Last 6 Months", "Last Year", "Custom Days"]
)

custom_days = None
if time_range == "Custom Days":
    custom_days = st.sidebar.number_input("Enter Days:", min_value=1, max_value=365, value=30)

# 3. SUBSCRIBER COUNT FILTER (User-Defined Range)
st.sidebar.subheader("3️⃣ Channel Subscribers")
enable_sub_filter = st.sidebar.checkbox("Enable Subscriber Filter", value=True)

if enable_sub_filter:
    col1, col2 = st.sidebar.columns(2)
    with col1:
        min_subs = st.number_input("Min:", min_value=0, value=0, step=100)
    with col2:
        max_subs = st.number_input("Max:", min_value=0, value=5000, step=100)
else:
    min_subs, max_subs = 0, float('inf')

# 4. CHANNEL AGE FILTER (User-Defined)
st.sidebar.subheader("4️⃣ Channel Age")
enable_age_filter = st.sidebar.checkbox("Enable Channel Age Filter", value=True)

if enable_age_filter:
    age_range = st.sidebar.selectbox(
        "Channel created within:",
        ["Last 30 Days", "Last 3 Months", "Last 6 Months", 
         "Last Year", "Last 2 Years", "Custom Days"]
    )
    
    custom_age_days = None
    if age_range == "Custom Days":
        custom_age_days = st.sidebar.number_input(
            "Enter Days (Age):", 
            min_value=1, 
            max_value=3650, 
            value=365
        )
else:
    age_range = None

# 5. RESULTS PER KEYWORD
st.sidebar.subheader("5️⃣ Results")
max_results = st.sidebar.slider("Max results per keyword:", 1, 50, 10)

# SEARCH BUTTON
st.sidebar.markdown("---")
search_btn = st.sidebar.button("🔍 Start Research", type="primary", use_container_width=True)

# ============================================
# HELPER FUNCTIONS
# ============================================

def get_published_after_date(option, custom=None):
    """Calculate the publishedAfter date for video search"""
    now = datetime.utcnow()
    time_map = {
        "Last 24 Hours": timedelta(hours=24),
        "Last 7 Days": timedelta(days=7),
        "Last 30 Days": timedelta(days=30),
        "Last 3 Months": timedelta(days=90),
        "Last 6 Months": timedelta(days=180),
        "Last Year": timedelta(days=365),
    }
    
    if option == "Custom Days" and custom:
        delta = timedelta(days=custom)
    else:
        delta = time_map.get(option, timedelta(days=30))
    
    return (now - delta).isoformat("T") + "Z"

def get_channel_age_cutoff(option, custom=None):
    """Calculate the channel creation date cutoff"""
    if not option:
        return None
    
    now = datetime.utcnow()
    age_map = {
        "Last 30 Days": timedelta(days=30),
        "Last 3 Months": timedelta(days=90),
        "Last 6 Months": timedelta(days=180),
        "Last Year": timedelta(days=365),
        "Last 2 Years": timedelta(days=730),
    }
    
    if option == "Custom Days" and custom:
        delta = timedelta(days=custom)
    else:
        delta = age_map.get(option, timedelta(days=365))
    
    return now - delta

def calculate_channel_age(created_date_str):
    """Calculate channel age in days"""
    try:
        created = datetime.strptime(created_date_str, "%Y-%m-%dT%H:%M:%SZ")
        age_days = (datetime.utcnow() - created).days
        return age_days, created
    except:
        return None, None

# ============================================
# MAIN CONTENT AREA
# ============================================

if not search_btn:
    # Display current configuration
    st.info("👈 Configure your search parameters in the sidebar and click **Start Research**")
    
    st.subheader("📋 Current Configuration:")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.write(f"**Keywords:** {len(keywords)}")
        st.write(f"**Time Range:** {time_range}")
    
    with col2:
        if enable_sub_filter:
            st.write(f"**Subscribers:** {min_subs:,} - {max_subs:,}")
        else:
            st.write(f"**Subscribers:** Any")
    
    with col3:
        if enable_age_filter:
            st.write(f"**Channel Age:** {age_range}")
        else:
            st.write(f"**Channel Age:** Any")

else:
    # Validate inputs
    if not keywords:
        st.error("❌ Please enter at least one keyword!")
    elif API_KEY == "Enter your API Key here":
        st.error("❌ Please add your YouTube API Key!")
    else:
        try:
            # Calculate date filters
            published_after = get_published_after_date(time_range, custom_days)
            channel_age_cutoff = get_channel_age_cutoff(age_range, custom_age_days) if enable_age_filter else None
            
            # Initialize results
            all_results = []
            progress = st.progress(0)
            status = st.empty()
            
            # Search each keyword
            total = len(keywords)
            for idx, keyword in enumerate(keywords):
                status.text(f"🔎 Searching: {keyword} ({idx+1}/{total})")
                progress.progress((idx+1)/total)
                
                # API Search Request
                search_params = {
                    "part": "snippet",
                    "q": keyword,
                    "type": "video",
                    "order": "date",
                    "publishedAfter": published_after,
                    "maxResults": max_results,
                    "key": API_KEY
                }
                
                response = requests.get(YOUTUBE_SEARCH_URL, params=search_params)
                data = response.json()
                
                # Check for errors
                if "error" in data:
                    st.error(f"API Error: {data['error']['message']}")
                    continue
                
                if "items" not in data or not data["items"]:
                    continue
                
                videos = data["items"]
                video_ids = [v["id"]["videoId"] for v in videos if "videoId" in v.get("id", {})]
                channel_ids = list(set([v["snippet"]["channelId"] for v in videos if "snippet" in v]))
                
                if not video_ids or not channel_ids:
                    continue
                
                # Fetch Video Statistics
                stats_response = requests.get(
                    YOUTUBE_VIDEO_URL,
                    params={"part": "statistics", "id": ",".join(video_ids), "key": API_KEY}
                )
                stats_data = stats_response.json()
                
                # Fetch Channel Information (with creation date)
                channel_response = requests.get(
                    YOUTUBE_CHANNEL_URL,
                    params={"part": "statistics,snippet", "id": ",".join(channel_ids), "key": API_KEY}
                )
                channel_data = channel_response.json()
                
                if "items" not in stats_data or "items" not in channel_data:
                    continue
                
                # Build lookup dictionaries
                channel_info = {}
                for ch in channel_data["items"]:
                    ch_id = ch["id"]
                    subs = int(ch["statistics"].get("subscriberCount", 0))
                    created = ch["snippet"].get("publishedAt", "")
                    age_days, created_dt = calculate_channel_age(created)
                    
                    channel_info[ch_id] = {
                        "name": ch["snippet"].get("title", "N/A"),
                        "subscribers": subs,
                        "created": created,
                        "age_days": age_days,
                        "created_dt": created_dt
                    }
                
                video_stats = {
                    v["id"]: {
                        "views": int(v["statistics"].get("viewCount", 0)),
                        "likes": int(v["statistics"].get("likeCount", 0)),
                        "comments": int(v["statistics"].get("commentCount", 0))
                    } for v in stats_data["items"]
                }
                
                # Process and filter results
                for video in videos:
                    vid_id = video["id"].get("videoId")
                    ch_id = video["snippet"]["channelId"]
                    
                    if not vid_id or ch_id not in channel_info or vid_id not in video_stats:
                        continue
                    
                    ch = channel_info[ch_id]
                    
                    # Apply subscriber filter
                    if enable_sub_filter:
                        if ch["subscribers"] < min_subs or ch["subscribers"] > max_subs:
                            continue
                    
                    # Apply channel age filter
                    if enable_age_filter and channel_age_cutoff and ch["created_dt"]:
                        if ch["created_dt"] < channel_age_cutoff:
                            continue
                    
                    # Add to results
                    all_results.append({
                        "keyword": keyword,
                        "video_title": video["snippet"].get("title", "N/A"),
                        "channel_name": ch["name"],
                        "video_url": f"https://www.youtube.com/watch?v={vid_id}",
                        "channel_url": f"https://www.youtube.com/channel/{ch_id}",
                        "views": video_stats[vid_id]["views"],
                        "likes": video_stats[vid_id]["likes"],
                        "comments": video_stats[vid_id]["comments"],
                        "subscribers": ch["subscribers"],
                        "channel_age_days": ch["age_days"] if ch["age_days"] else "N/A",
                        "published": video["snippet"].get("publishedAt", "N/A")[:10]
                    })
            
            # Clear progress
            progress.empty()
            status.empty()
            
            # Display Results
            if all_results:
                st.success(f"✅ Found **{len(all_results)}** videos from **{len(set([r['channel_name'] for r in all_results]))}** unique channels!")
                
                # Summary Stats
                st.subheader("📊 Summary Statistics")
                col1, col2, col3, col4 = st.columns(4)
                
                col1.metric("Total Videos", len(all_results))
                col2.metric("Unique Channels", len(set([r['channel_name'] for r in all_results])))
                col3.metric("Total Views", f"{sum([r['views'] for r in all_results]):,}")
                col4.metric("Avg Subscribers", f"{int(sum([r['subscribers'] for r in all_results])/len(all_results)):,}")
                
                # Sort Options
                st.subheader("📋 Detailed Results")
                sort_option = st.selectbox(
                    "Sort by:",
                    ["Views (High to Low)", "Subscribers (Low to High)", "Channel Age (Newest)", "Published Date (Recent)"]
                )
                
                if "Views (High" in sort_option:
                    all_results.sort(key=lambda x: x["views"], reverse=True)
                elif "Subscribers (Low" in sort_option:
                    all_results.sort(key=lambda x: x["subscribers"])
                elif "Channel Age" in sort_option:
                    all_results.sort(key=lambda x: x["channel_age_days"] if isinstance(x["channel_age_days"], int) else 999999)
                else:
                    all_results.sort(key=lambda x: x["published"], reverse=True)
                
                # Display Results
                for i, r in enumerate(all_results, 1):
                    with st.expander(f"#{i} - {r['video_title'][:70]}..."):
                        col1, col2 = st.columns([2, 1])
                        
                        with col1:
                            st.markdown(f"**🎥 Video:** [{r['video_title']}]({r['video_url']})")
                            st.markdown(f"**📺 Channel:** [{r['channel_name']}]({r['channel_url']})")
                            st.markdown(f"**🔑 Keyword:** {r['keyword']}")
                        
                        with col2:
                            st.metric("👁️ Views", f"{r['views']:,}")
                            st.metric("👥 Subscribers", f"{r['subscribers']:,}")
                            st.metric("⏱️ Channel Age", f"{r['channel_age_days']} days" if isinstance(r['channel_age_days'], int) else "N/A")
                
                # Export to CSV
                st.subheader("📥 Export Data")
                import io
                csv = io.StringIO()
                csv.write("Keyword,Video Title,Channel Name,Subscribers,Views,Likes,Comments,Channel Age (Days),Video URL,Channel URL\n")
                for r in all_results:
                    csv.write(f"{r['keyword']},{r['video_title']},{r['channel_name']},{r['subscribers']},{r['views']},{r['likes']},{r['comments']},{r['channel_age_days']},{r['video_url']},{r['channel_url']}\n")
                
                st.download_button(
                    "📥 Download CSV",
                    data=csv.getvalue(),
                    file_name=f"youtube_research_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv"
                )
            else:
                st.warning("⚠️ No results found. Try adjusting your filters.")
                
        except Exception as e:
            st.error(f"❌ Error: {str(e)}")
            st.exception(e)

# Footer
st.sidebar.markdown("---")
st.sidebar.info("💡 **Tip:** Use specific keywords and adjust filters to find emerging creators in your niche!")
