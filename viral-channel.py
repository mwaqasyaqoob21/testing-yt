import streamlit as st
import requests
from datetime import datetime, timedelta
from difflib import SequenceMatcher
import re
from collections import Counter
import isodate  # For parsing YouTube duration format

# YouTube API Configuration
API_KEY = "AIzaSyAMSPSOQaPGAia_SxtMzcsL72w-cuSgh9U"
YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
YOUTUBE_VIDEO_URL = "https://www.googleapis.com/youtube/v3/videos"
YOUTUBE_CHANNEL_URL = "https://www.googleapis.com/youtube/v3/channels"

# Initialize Session State
if 'search_results' not in st.session_state:
    st.session_state.search_results = []
if 'search_completed' not in st.session_state:
    st.session_state.search_completed = False
if 'similarity_analysis' not in st.session_state:
    st.session_state.similarity_analysis = False

# Page Configuration
st.set_page_config(page_title="YouTube Research Tool", page_icon="🔍", layout="wide")
st.title("🔍 YouTube Channel Research Tool")
st.markdown("**Discover new YouTube channels based on your custom criteria**")

# ============================================
# DURATION PARSING FUNCTIONS
# ============================================

def parse_duration(duration_str):
    """Parse ISO 8601 duration format to seconds"""
    try:
        duration = isodate.parse_duration(duration_str)
        return int(duration.total_seconds())
    except:
        return 0

def format_duration(seconds):
    """Format seconds to readable duration"""
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        minutes = seconds // 60
        secs = seconds % 60
        return f"{minutes}m {secs}s"
    else:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        return f"{hours}h {minutes}m"

def is_short_video(duration_seconds):
    """Determine if video is a YouTube Short (<=60 seconds)"""
    return duration_seconds <= 60

# ============================================
# SIMILARITY DETECTION FUNCTIONS
# ============================================

def calculate_text_similarity(text1, text2):
    """Calculate similarity ratio between two texts (0-1)"""
    return SequenceMatcher(None, text1.lower(), text2.lower()).ratio()

def extract_keywords(text, top_n=10):
    """Extract important keywords from text"""
    common_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
                    'of', 'with', 'by', 'from', 'up', 'about', 'into', 'through', 'during',
                    'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had',
                    'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might',
                    'i', 'you', 'he', 'she', 'it', 'we', 'they', 'my', 'your', 'his', 'her',
                    'part', 'update', 'story', 'reddit'}
    
    words = re.findall(r'\b[a-z]+\b', text.lower())
    filtered_words = [w for w in words if w not in common_words and len(w) > 3]
    
    word_freq = Counter(filtered_words)
    return [word for word, _ in word_freq.most_common(top_n)]

def calculate_keyword_overlap(keywords1, keywords2):
    """Calculate overlap between two keyword lists"""
    if not keywords1 or not keywords2:
        return 0
    set1, set2 = set(keywords1), set(keywords2)
    intersection = len(set1 & set2)
    union = len(set1 | set2)
    return intersection / union if union > 0 else 0

def find_similar_videos(target_video, all_videos, threshold=0.3):
    """Find videos similar to the target video"""
    similar = []
    target_title = target_video['video_title']
    target_desc = target_video.get('description', '')
    target_keywords = extract_keywords(target_title + ' ' + target_desc)
    
    for video in all_videos:
        if video['video_url'] == target_video['video_url']:
            continue
        
        title_sim = calculate_text_similarity(target_title, video['video_title'])
        
        video_keywords = extract_keywords(video['video_title'] + ' ' + video.get('description', ''))
        keyword_sim = calculate_keyword_overlap(target_keywords, video_keywords)
        
        similarity_score = (title_sim * 0.6) + (keyword_sim * 0.4)
        
        if similarity_score >= threshold:
            similar.append({
                'video': video,
                'similarity_score': similarity_score,
                'title_similarity': title_sim,
                'keyword_similarity': keyword_sim
            })
    
    similar.sort(key=lambda x: x['similarity_score'], reverse=True)
    return similar

def group_similar_content(all_videos, threshold=0.35):
    """Group videos into clusters of similar content"""
    clusters = []
    processed = set()
    
    for i, video in enumerate(all_videos):
        if i in processed:
            continue
        
        cluster = [video]
        processed.add(i)
        
        for j, other_video in enumerate(all_videos):
            if j in processed or i == j:
                continue
            
            title_sim = calculate_text_similarity(video['video_title'], other_video['video_title'])
            
            video_keywords = extract_keywords(video['video_title'])
            other_keywords = extract_keywords(other_video['video_title'])
            keyword_sim = calculate_keyword_overlap(video_keywords, other_keywords)
            
            combined_sim = (title_sim * 0.6) + (keyword_sim * 0.4)
            
            if combined_sim >= threshold:
                cluster.append(other_video)
                processed.add(j)
        
        clusters.append(cluster)
    
    clusters.sort(key=len, reverse=True)
    return clusters

def detect_trending_topics(all_videos, min_occurrence=2):
    """Detect trending topics across all videos"""
    all_keywords = []
    
    for video in all_videos:
        keywords = extract_keywords(video['video_title'])
        all_keywords.extend(keywords)
    
    keyword_freq = Counter(all_keywords)
    trending = [(word, count) for word, count in keyword_freq.most_common(20) 
                if count >= min_occurrence]
    
    return trending

# ============================================
# SIDEBAR - INPUT PARAMETERS
# ============================================
st.sidebar.header("⚙️ Search Configuration")

# 1. KEYWORD INPUT
st.sidebar.subheader("1️⃣ Keywords")
keywords_input = st.sidebar.text_area(
    "Enter Keywords (one per line):",
    value="Reddit Stories\nCheating Stories\nRelationship Advice",
    height=150,
    help="Enter one keyword per line to search for relevant videos"
)
keywords = [k.strip() for k in keywords_input.split('\n') if k.strip()]

# 2. VIDEO TYPE FILTER
st.sidebar.subheader("2️⃣ Video Type")
video_type_filter = st.sidebar.radio(
    "Show:",
    ["All Videos", "Shorts Only (≤60s)", "Regular Videos Only (>60s)"],
    help="Filter results by video duration"
)

# 3. TIME RANGE FILTER
st.sidebar.subheader("3️⃣ Video Upload Time")
time_range = st.sidebar.selectbox(
    "Videos uploaded within:",
    ["Last 24 Hours", "Last 7 Days", "Last 30 Days", "Last 3 Months", 
     "Last 6 Months", "Last Year", "Custom Days"]
)

custom_days = None
if time_range == "Custom Days":
    custom_days = st.sidebar.number_input("Enter Days:", min_value=1, max_value=365, value=30)

# 4. SUBSCRIBER COUNT FILTER
st.sidebar.subheader("4️⃣ Channel Subscribers")
enable_sub_filter = st.sidebar.checkbox("Enable Subscriber Filter", value=True)

if enable_sub_filter:
    col1, col2 = st.sidebar.columns(2)
    with col1:
        min_subs = st.number_input("Min:", min_value=0, value=0, step=100)
    with col2:
        max_subs = st.number_input("Max:", min_value=0, value=5000, step=100)
else:
    min_subs, max_subs = 0, float('inf')

# 5. CHANNEL AGE FILTER
st.sidebar.subheader("5️⃣ Channel Age")
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

# 6. RESULTS PER KEYWORD
st.sidebar.subheader("6️⃣ Results")
max_results = st.sidebar.slider("Max results per keyword:", 1, 50, 10)

# 7. SIMILARITY DETECTION
st.sidebar.subheader("7️⃣ Similarity Analysis")
enable_similarity = st.sidebar.checkbox("Enable Similarity Detection", value=True, 
                                        help="Find and group similar content")
if enable_similarity:
    similarity_threshold = st.sidebar.slider(
        "Similarity Threshold:",
        min_value=0.1,
        max_value=0.9,
        value=0.35,
        step=0.05,
        help="Higher = stricter matching (0.3-0.4 recommended)"
    )

# SEARCH BUTTON
st.sidebar.markdown("---")
search_btn = st.sidebar.button("🔍 Start Research", type="primary", use_container_width=True)

# CLEAR RESULTS BUTTON
if st.session_state.search_completed:
    if st.sidebar.button("🗑️ Clear Results", use_container_width=True):
        st.session_state.search_results = []
        st.session_state.search_completed = False
        st.session_state.similarity_analysis = False
        st.rerun()

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

def perform_search(keywords, published_after, channel_age_cutoff, enable_age_filter, 
                   enable_sub_filter, min_subs, max_subs, max_results, API_KEY):
    """Perform the YouTube search and return results"""
    all_results = []
    progress = st.progress(0)
    status = st.empty()
    
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
        
        # Fetch Video Statistics AND Duration (contentDetails)
        stats_response = requests.get(
            YOUTUBE_VIDEO_URL,
            params={"part": "statistics,snippet,contentDetails", "id": ",".join(video_ids), "key": API_KEY}
        )
        stats_data = stats_response.json()
        
        # Fetch Channel Information
        channel_response = requests.get(
            YOUTUBE_CHANNEL_URL,
            params={"part": "statistics,snippet", "id": ",".join(channel_ids), "key": API_KEY}
        )
        channel_data = channel_response.json()
        
        if "items" not in stats_data or "items" not in channel_data:
            continue
        
        # Build channel lookup
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
        
        # Build video stats lookup with DURATION
        video_stats = {}
        for v in stats_data["items"]:
            duration_iso = v.get("contentDetails", {}).get("duration", "PT0S")
            duration_seconds = parse_duration(duration_iso)
            
            video_stats[v["id"]] = {
                "views": int(v["statistics"].get("viewCount", 0)),
                "likes": int(v["statistics"].get("likeCount", 0)),
                "comments": int(v["statistics"].get("commentCount", 0)),
                "description": v["snippet"].get("description", "")[:300],
                "tags": v["snippet"].get("tags", []),
                "duration_seconds": duration_seconds,
                "duration_formatted": format_duration(duration_seconds),
                "is_short": is_short_video(duration_seconds)
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
                "description": video_stats[vid_id]["description"],
                "tags": video_stats[vid_id]["tags"],
                "duration_seconds": video_stats[vid_id]["duration_seconds"],
                "duration_formatted": video_stats[vid_id]["duration_formatted"],
                "is_short": video_stats[vid_id]["is_short"],
                "subscribers": ch["subscribers"],
                "channel_age_days": ch["age_days"] if ch["age_days"] else "N/A",
                "published": video["snippet"].get("publishedAt", "N/A")[:10]
            })
    
    progress.empty()
    status.empty()
    
    return all_results

# ============================================
# MAIN CONTENT AREA
# ============================================

# If search button is clicked, perform new search
if search_btn:
    if not keywords:
        st.error("❌ Please enter at least one keyword!")
    elif API_KEY == "Enter your API Key here":
        st.error("❌ Please add your YouTube API Key!")
    else:
        try:
            published_after = get_published_after_date(time_range, custom_days)
            channel_age_cutoff = get_channel_age_cutoff(age_range, custom_age_days) if enable_age_filter else None
            
            st.session_state.search_results = perform_search(
                keywords, published_after, channel_age_cutoff, enable_age_filter,
                enable_sub_filter, min_subs, max_subs, max_results, API_KEY
            )
            st.session_state.search_completed = True
            st.session_state.similarity_analysis = enable_similarity
            
        except Exception as e:
            st.error(f"❌ Error: {str(e)}")
            st.exception(e)

# Display results from session state
if st.session_state.search_completed and st.session_state.search_results:
    all_results = st.session_state.search_results
    
    # Filter by video type
    if video_type_filter == "Shorts Only (≤60s)":
        filtered_results = [r for r in all_results if r['is_short']]
        filter_emoji = "📱"
    elif video_type_filter == "Regular Videos Only (>60s)":
        filtered_results = [r for r in all_results if not r['is_short']]
        filter_emoji = "🎬"
    else:
        filtered_results = all_results
        filter_emoji = "🎥"
    
    # Separate shorts and regular videos for stats
    shorts = [r for r in all_results if r['is_short']]
    regular_videos = [r for r in all_results if not r['is_short']]
    
    st.success(f"{filter_emoji} Found **{len(filtered_results)}** videos from **{len(set([r['channel_name'] for r in filtered_results]))}** unique channels!")
    
    # Summary Stats with Shorts/Regular breakdown
    st.subheader("📊 Summary Statistics")
    col1, col2, col3, col4, col5 = st.columns(5)
    
    col1.metric("Total Videos", len(all_results))
    col2.metric("📱 Shorts", len(shorts), delta=f"{len(shorts)/max(len(all_results),1)*100:.0f}%")
    col3.metric("🎬 Regular", len(regular_videos), delta=f"{len(regular_videos)/max(len(all_results),1)*100:.0f}%")
    col4.metric("Unique Channels", len(set([r['channel_name'] for r in all_results])))
    col5.metric("Total Views", f"{sum([r['views'] for r in all_results]):,}")
    
    # ============================================
    # TABS: Shorts vs Regular Videos
    # ============================================
    
    main_tab1, main_tab2, main_tab3, main_tab4 = st.tabs([
        f"📱 Shorts ({len(shorts)})", 
        f"🎬 Regular Videos ({len(regular_videos)})",
        "🔗 Similarity Analysis",
        "📥 Export Data"
    ])
    
    # ============================================
    # TAB 1: SHORTS VIDEOS
    # ============================================
    with main_tab1:
        if shorts:
            st.subheader(f"📱 YouTube Shorts (≤60 seconds) - {len(shorts)} results")
            
            # Shorts-specific stats
            col1, col2, col3 = st.columns(3)
            col1.metric("Total Views", f"{sum([r['views'] for r in shorts]):,}")
            col2.metric("Avg Views/Short", f"{int(sum([r['views'] for r in shorts])/len(shorts)):,}")
            col3.metric("Unique Channels", len(set([r['channel_name'] for r in shorts])))
            
            # Sort options for shorts
            sort_shorts = st.selectbox(
                "Sort Shorts by:",
                ["Views (High to Low)", "Subscribers (Low to High)", 
                 "Published Date (Recent)", "Engagement Rate (High to Low)"],
                key="sort_shorts"
            )
            
            sorted_shorts = shorts.copy()
            
            if "Views (High" in sort_shorts:
                sorted_shorts.sort(key=lambda x: x["views"], reverse=True)
            elif "Subscribers (Low" in sort_shorts:
                sorted_shorts.sort(key=lambda x: x["subscribers"])
            elif "Engagement Rate" in sort_shorts:
                sorted_shorts.sort(key=lambda x: (x["likes"] + x["comments"]) / max(x["views"], 1), reverse=True)
            else:
                sorted_shorts.sort(key=lambda x: x["published"], reverse=True)
            
            # Display shorts
            for i, r in enumerate(sorted_shorts, 1):
                with st.expander(f"#{i} - {r['video_title'][:60]}... | ⏱️ {r['duration_formatted']}"):
                    col1, col2 = st.columns([2, 1])
                    
                    with col1:
                        st.markdown(f"**🎥 Video:** [{r['video_title']}]({r['video_url']})")
                        st.markdown(f"**📺 Channel:** [{r['channel_name']}]({r['channel_url']})")
                        st.markdown(f"**🔑 Keyword:** {r['keyword']}")
                        st.markdown(f"**📅 Published:** {r['published']} | ⏱️ Duration: **{r['duration_formatted']}**")
                        
                        if r.get('description'):
                            st.caption(f"📝 {r['description'][:120]}...")
                    
                    with col2:
                        st.metric("👁️ Views", f"{r['views']:,}")
                        st.metric("👍 Likes", f"{r['likes']:,}")
                        st.metric("💬 Comments", f"{r['comments']:,}")
                        engagement = (r['likes'] + r['comments']) / max(r['views'], 1) * 100
                        st.metric("📈 Engagement", f"{engagement:.2f}%")
                        st.metric("👥 Subs", f"{r['subscribers']:,}")
        else:
            st.info("No YouTube Shorts found in results")
    
    # ============================================
    # TAB 2: REGULAR VIDEOS
    # ============================================
    with main_tab2:
        if regular_videos:
            st.subheader(f"🎬 Regular Videos (>60 seconds) - {len(regular_videos)} results")
            
            # Regular videos stats
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Total Views", f"{sum([r['views'] for r in regular_videos]):,}")
            col2.metric("Avg Views/Video", f"{int(sum([r['views'] for r in regular_videos])/len(regular_videos)):,}")
            col3.metric("Avg Duration", format_duration(int(sum([r['duration_seconds'] for r in regular_videos])/len(regular_videos))))
            col4.metric("Unique Channels", len(set([r['channel_name'] for r in regular_videos])))
            
            # Sort options for regular videos
            sort_regular = st.selectbox(
                "Sort Regular Videos by:",
                ["Views (High to Low)", "Subscribers (Low to High)", 
                 "Duration (Longest)", "Published Date (Recent)", 
                 "Engagement Rate (High to Low)"],
                key="sort_regular"
            )
            
            sorted_regular = regular_videos.copy()
            
            if "Views (High" in sort_regular:
                sorted_regular.sort(key=lambda x: x["views"], reverse=True)
            elif "Subscribers (Low" in sort_regular:
                sorted_regular.sort(key=lambda x: x["subscribers"])
            elif "Duration" in sort_regular:
                sorted_regular.sort(key=lambda x: x["duration_seconds"], reverse=True)
            elif "Engagement Rate" in sort_regular:
                sorted_regular.sort(key=lambda x: (x["likes"] + x["comments"]) / max(x["views"], 1), reverse=True)
            else:
                sorted_regular.sort(key=lambda x: x["published"], reverse=True)
            
            # Display regular videos
            for i, r in enumerate(sorted_regular, 1):
                with st.expander(f"#{i} - {r['video_title'][:60]}... | ⏱️ {r['duration_formatted']}"):
                    col1, col2 = st.columns([2, 1])
                    
                    with col1:
                        st.markdown(f"**🎥 Video:** [{r['video_title']}]({r['video_url']})")
                        st.markdown(f"**📺 Channel:** [{r['channel_name']}]({r['channel_url']})")
                        st.markdown(f"**🔑 Keyword:** {r['keyword']}")
                        st.markdown(f"**📅 Published:** {r['published']} | ⏱️ Duration: **{r['duration_formatted']}**")
                        
                        if r.get('description'):
                            st.caption(f"📝 {r['description'][:150]}...")
                        
                        if r.get('tags'):
                            tags_str = ", ".join(r['tags'][:5])
                            st.caption(f"🏷️ Tags: {tags_str}")
                    
                    with col2:
                        st.metric("👁️ Views", f"{r['views']:,}")
                        st.metric("👍 Likes", f"{r['likes']:,}")
                        st.metric("💬 Comments", f"{r['comments']:,}")
                        engagement = (r['likes'] + r['comments']) / max(r['views'], 1) * 100
                        st.metric("📈 Engagement", f"{engagement:.2f}%")
                        st.metric("👥 Subscribers", f"{r['subscribers']:,}")
                        st.metric("⏱️ Channel Age", 
                                 f"{r['channel_age_days']} days" if isinstance(r['channel_age_days'], int) else "N/A")
        else:
            st.info("No regular videos found in results")
    
    # ============================================
    # TAB 3: SIMILARITY ANALYSIS
    # ============================================
    with main_tab3:
        if st.session_state.similarity_analysis and enable_similarity:
            st.header("🔗 Similarity Analysis")
            
            analysis_tab1, analysis_tab2, analysis_tab3 = st.tabs([
                "📊 Trending Topics", 
                "🎯 Content Clusters", 
                "🔍 Find Similar"
            ])
            
            # Trending Topics
            with analysis_tab1:
                st.subheader("🔥 Trending Topics Across Results")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write("**📱 Shorts Topics:**")
                    if shorts:
                        trending_shorts = detect_trending_topics(shorts, min_occurrence=2)
                        if trending_shorts:
                            for topic, count in trending_shorts[:8]:
                                st.metric(topic.title(), f"{count} videos")
                        else:
                            st.info("Not enough data")
                    else:
                        st.info("No shorts found")
                
                with col2:
                    st.write("**🎬 Regular Videos Topics:**")
                    if regular_videos:
                        trending_regular = detect_trending_topics(regular_videos, min_occurrence=2)
                        if trending_regular:
                            for topic, count in trending_regular[:8]:
                                st.metric(topic.title(), f"{count} videos")
                        else:
                            st.info("Not enough data")
                    else:
                        st.info("No regular videos found")
            
            # Content Clusters
            with analysis_tab2:
                st.subheader("🎯 Similar Content Groups")
                
                cluster_type = st.radio(
                    "Analyze:",
                    ["All Videos", "Shorts Only", "Regular Videos Only"]
                )
                
                if cluster_type == "Shorts Only":
                    cluster_data = shorts
                elif cluster_type == "Regular Videos Only":
                    cluster_data = regular_videos
                else:
                    cluster_data = filtered_results
                
                if cluster_data:
                    clusters = group_similar_content(cluster_data, threshold=similarity_threshold)
                    significant_clusters = [c for c in clusters if len(c) > 1]
                    
                    if significant_clusters:
                        st.write(f"Found **{len(significant_clusters)}** groups of similar content:")
                        
                        for i, cluster in enumerate(significant_clusters[:10], 1):
                            with st.expander(f"📁 Cluster {i} - {len(cluster)} similar videos"):
                                for video in cluster:
                                    duration_badge = "📱" if video['is_short'] else "🎬"
                                    st.markdown(f"{duration_badge} [{video['video_title']}]({video['video_url']}) | "
                                              f"⏱️ {video['duration_formatted']} | "
                                              f"👁️ {video['views']:,} | "
                                              f"👥 {video['subscribers']:,} subs")
                    else:
                        st.info("No significant content clusters found. Try lowering the similarity threshold.")
                else:
                    st.info("No videos to analyze")
            
            # Find Similar
            with analysis_tab3:
                st.subheader("🔍 Find Similar Videos")
                
                if filtered_results:
                    video_options = [f"{r['video_title'][:50]}... ({r['duration_formatted']}) - {r['views']:,} views" 
                                   for r in filtered_results]
                    
                    selected_video_idx = st.selectbox(
                        "Select a video to find similar content:",
                        range(len(filtered_results)),
                        format_func=lambda x: video_options[x]
                    )
                    
                    if st.button("Find Similar Videos"):
                        target = filtered_results[selected_video_idx]
                        similar = find_similar_videos(target, filtered_results, threshold=similarity_threshold)
                        
                        if similar:
                            st.success(f"Found {len(similar)} similar videos:")
                            
                            for sim in similar[:10]:
                                v = sim['video']
                                score = sim['similarity_score']
                                duration_badge = "📱" if v['is_short'] else "🎬"
                                
                                with st.container():
                                    col1, col2 = st.columns([3, 1])
                                    with col1:
                                        st.markdown(f"{duration_badge} **[{v['video_title']}]({v['video_url']})**")
                                        st.caption(f"Channel: {v['channel_name']} | ⏱️ {v['duration_formatted']} | {v['views']:,} views")
                                    with col2:
                                        st.metric("Match", f"{score*100:.0f}%")
                                    st.markdown("---")
                        else:
                            st.warning("No similar videos found. Try lowering the similarity threshold.")
                else:
                    st.info("No videos available for analysis")
        else:
            st.info("Enable Similarity Detection in the sidebar to use this feature")
    
    # ============================================
    # TAB 4: EXPORT DATA
    # ============================================
    with main_tab4:
        st.subheader("📥 Export Data")
        
        col1, col2, col3 = st.columns(3)
        
        # Export All Results
        with col1:
            import io
            csv_all = io.StringIO()
            csv_all.write("Video Type,Keyword,Video Title,Channel Name,Duration,Subscribers,Views,Likes,Comments,Engagement Rate,Channel Age (Days),Published Date,Video URL,Channel URL\n")
            for r in all_results:
                video_type = "Short" if r['is_short'] else "Regular"
                video_title = r['video_title'].replace(',', ';').replace('\n', ' ')
                channel_name = r['channel_name'].replace(',', ';')
                engagement = (r['likes'] + r['comments']) / max(r['views'], 1) * 100
                csv_all.write(f"{video_type},{r['keyword']},{video_title},{channel_name},{r['duration_formatted']},{r['subscribers']},{r['views']},{r['likes']},{r['comments']},{engagement:.2f}%,{r['channel_age_days']},{r['published']},{r['video_url']},{r['channel_url']}\n")
            
            st.download_button(
                "📥 Download All Results",
                data=csv_all.getvalue(),
                file_name=f"youtube_all_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )
        
        # Export Shorts Only
        with col2:
            if shorts:
                csv_shorts = io.StringIO()
                csv_shorts.write("Keyword,Video Title,Channel Name,Duration,Subscribers,Views,Likes,Comments,Video URL\n")
                for r in shorts:
                    video_title = r['video_title'].replace(',', ';').replace('\n', ' ')
                    channel_name = r['channel_name'].replace(',', ';')
                    csv_shorts.write(f"{r['keyword']},{video_title},{channel_name},{r['duration_formatted']},{r['subscribers']},{r['views']},{r['likes']},{r['comments']},{r['video_url']}\n")
                
                st.download_button(
                    "📱 Download Shorts Only",
                    data=csv_shorts.getvalue(),
                    file_name=f"youtube_shorts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv"
                )
            else:
                st.info("No shorts to export")
        
        # Export Regular Videos Only
        with col3:
            if regular_videos:
                csv_regular = io.StringIO()
                csv_regular.write("Keyword,Video Title,Channel Name,Duration,Subscribers,Views,Likes,Comments,Video URL\n")
                for r in regular_videos:
                    video_title = r['video_title'].replace(',', ';').replace('\n', ' ')
                    channel_name = r['channel_name'].replace(',', ';')
                    csv_regular.write(f"{r['keyword']},{video_title},{channel_name},{r['duration_formatted']},{r['subscribers']},{r['views']},{r['likes']},{r['comments']},{r['video_url']}\n")
                
                st.download_button(
                    "🎬 Download Regular Videos",
                    data=csv_regular.getvalue(),
                    file_name=f"youtube_regular_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv"
                )
            else:
                st.info("No regular videos to export")

elif st.session_state.search_completed and not st.session_state.search_results:
    st.warning("⚠️ No results found. Try adjusting your filters.")

else:
    # Display current configuration
    st.info("👈 Configure your search parameters in the sidebar and click **Start Research**")
    
    st.subheader("📋 Current Configuration:")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.write(f"**Keywords:** {len(keywords)}")
        st.write(f"**Video Type:** {video_type_filter}")
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

# Footer
st.sidebar.markdown("---")
st.sidebar.info("💡 **Tip:** Use video type filter to focus on Shorts or Regular videos separately!")
