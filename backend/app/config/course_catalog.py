"""
Course catalog: maps course titles to topic-based categories.

Course names are kept exactly as provided by the platform.
Track assignments (DA / DS / DE) are NOT included here — they will be
handled separately during data embedding.
"""

from typing import Dict, List, Optional

# ---- Category constants ----
DATA_ANALYTICS = "Data & Analytics"
PROGRAMMING = "Programming"
AI_DATA_SCIENCE = "AI & Data Science"
AI_AUTOMATION = "AI & Automation"
DATA_ENGINEERING = "Data Engineering"
SOFT_SKILLS = "Soft Skills"
CAREER = "Career"
PROJECTS = "Projects"
LIVE_SESSIONS = "Live Sessions"
WELCOME = "Welcome"

# ---- Master catalog: course_title → category ----
COURSE_CATALOG: Dict[str, str] = {
    # Core Skills
    "Excel: Mother of Business Intelligence":                                       DATA_ANALYTICS,
    "Python: Beginner to Advanced For Data Professionals":                          PROGRAMMING,
    "SQL Beginner to Advanced For Data Professionals":                              PROGRAMMING,
    "SQL for Data Science":                                                         PROGRAMMING,
    "Math and Statistics For AI, Data Science":                                     AI_DATA_SCIENCE,

    # BI & Visualization
    "Get Job Ready: Power BI Data Analytics for All Levels 3.0":                    DATA_ANALYTICS,
    "DA 2.0: The AI Enabled Data Analyst":                                          DATA_ANALYTICS,
    "Microsoft Fabric Mini: For Data Analysts":                                     DATA_ANALYTICS,
    "Tableau Mini":                                                                 DATA_ANALYTICS,

    # AI & Machine Learning
    "Deep Learning: Beginner to Advanced":                                          AI_DATA_SCIENCE,
    "Master Machine Learning for Data Science & AI: Beginner to Advanced":          AI_DATA_SCIENCE,
    "Natural Language Processing":                                                  AI_DATA_SCIENCE,

    # AI & Automation
    "AI Toolkit For Professionals":                                                 AI_AUTOMATION,
    "Gen AI":                                                                       AI_AUTOMATION,
    "Gen AI to Agentic AI with Business Projects":                                  AI_AUTOMATION,
    "AI Automation for Data Professionals":                                          AI_AUTOMATION,

    # Data Engineering
    "Data Engineering Basics for Data Analysts":                                    DATA_ENGINEERING,
    "Data Engineering Foundations - I":                                              DATA_ENGINEERING,
    "Data Engineering Foundations - II":                                             DATA_ENGINEERING,
    "Apache Spark Fundamentals":                                                    DATA_ENGINEERING,
    "Snowflake Fundamentals":                                                       DATA_ENGINEERING,
    "Airflow Fundamentals":                                                         DATA_ENGINEERING,
    "Kafka and Flink Fundamentals":                                                 DATA_ENGINEERING,
    "Practice Room 4: Snowflake, Airflow":                                          DATA_ENGINEERING,
    "Real Time Fleet Telemetry Streaming and Analytics":                            DATA_ENGINEERING,

    # Projects
    "Project: Build your first ETL Pipeline using AWS":                             PROJECTS,
    "Project: Build E-commerce Data Pipeline using Spark & Databricks":             PROJECTS,
    "Project 2: Build E-commerce Data Pipeline using Spark & Databricks":           PROJECTS,
    "Project: Securities Pricing Data Pipeline using Docker, Airflow, Snowflake and AWS": PROJECTS,
    "HyperDelivery Project: Real-Time Streaming Analytics on Azure":                PROJECTS,
    "Supplementary Learning: Projects & Case Studies":                              PROJECTS,
    "SQL Projects [Optional]":                                                      PROJECTS,
    "Python Projects [Optional]":                                                   PROJECTS,

    # Soft Skills
    "Mastering Communication & Stakeholder Management":                             SOFT_SKILLS,
    "Mastering Time Management & Deep Work":                                        SOFT_SKILLS,
    "Personal Branding (LinkedIn & Beyond) for All Professionals":                  SOFT_SKILLS,

    # Career & Credibility
    "Start Applying for Jobs":                                                      CAREER,
    "Start Applying for Jobs -DS":                                                  CAREER,
    "Start Applying for Jobs - DE":                                                 CAREER,
    "Interview Preparation / Job Assistance":                                       CAREER,
    "Interview Preparation / Job Assistance - DS":                                  CAREER,
    "Interview Preparation / Job Assistance - DE":                                  CAREER,
    "Start Building Your Online Credibility":                                       CAREER,
    "Building Online Credibility, Portfolio Projects & ATS Resume":                 CAREER,
    "Online Credibility":                                                           CAREER,
    "Online Credibility & Domain Knowledge Course":                                 CAREER,
    "Job Assistance Portal, ATS Resume & Portfolio Website":                        CAREER,
    "ATS Resume & Portfolio Projects: DE":                                          CAREER,
    "Build In Public":                                                              CAREER,
    "Virtual Internship":                                                           CAREER,
    "Virtual Internship 2":                                                         CAREER,

    # Welcome / Orientation
    "Welcome to The Bootcamp Experience":                                           WELCOME,
    "Welcome to The Gen AI and Data Science Bootcamp Experience":                   WELCOME,
    "Welcome to The Data Engineering Bootcamp Experience":                          WELCOME,

    # Live Sessions
    "Live Webinar":                                                                 LIVE_SESSIONS,
    "Live Webinars":                                                                LIVE_SESSIONS,
    "Live Problem-Solving Sessions":                                                LIVE_SESSIONS,
}


# ---- Chapter overrides for courses with bundled/mis-ordered content ----
# Maps course_title -> ordered list of correct chapter titles.
# Chapters not in this list will be excluded. Order determines display order.
CHAPTER_OVERRIDES: Dict[str, List[str]] = {
    "Master Machine Learning for Data Science & AI: Beginner to Advanced": [
        "Welcome to Machine Learning Experience",
        "Machine Learning Basics",
        "Supervised Machine Learning: Regression",
        "Supervised Machine Learning: Classification",
        "Ensemble Learning",
        "Model Evaluation & Fine Tuning",
        "ML Project Life Cycle",
        "Feature Engineering",
        "Unsupervised Learning",
        "Project 1: Healthcare Premium Prediction (Regression)",
        "Project 2: Credit Risk Modelling (Classification)",
        "ML Ops & Cloud Tools",
        "Final QuizMandatory",
        "ML Interview Question Bank",
        "What's Next",
        "AI Family Tree",
    ],
    "Get Job Ready: Power BI Data Analytics for All Levels 3.0": [
        "Welcome to The Power BI Experience",
        "Power BI Basics: Getting Started",
        "Project Planning and Scoping",
        "Power BI Basics: Data collection, Exploration & Validation",
        "Power BI Basics: Data Transformation in Power Query",
        "Get Your DAX Fear Removed",
        "Power BI Advanced: Data Modeling & Calculated Columns",
        "Power BI Advanced: Build Finance View",
        "Power BI Advanced: Build Sales, Marketing & Supply Chain View",
        "Power BI Advanced: Designing an Effective Dashboard",
        "Power BI Advanced: Data Validation Set Up in PBI Service",
        "Stakeholder review & Feedback implementation",
        "Deploying the Solution: Power BI Service",
        "Practice Exercise Solutions",
        "More Practice",
        "PBI Monthly Update Tasks",
        "PL-300 Exam Question Bank",
        "Course Completion Test",
        "What's Next?",
    ],
    "AI Toolkit For Professionals": [
        "Introduction",
        "AI Basics: The Practical & No-Nonsense Stuff",
        "Enhance your Learning Experience",
        "Register for Live Workshop: Submit your use cases",
        "Get hands-on: Use AI tools for General & Creative tasks",
        "Get hands-on: Use AI tools for Enhanced Productivity & Automation",
        "Next Steps: Apply these Skills at Your Work",
        "Bonus Section",
        "Recordings: Monthly Workshops",
        "Course Completion Certificate",
        "What are companies expecting from professionals in this AI wave?",
    ],
    "Deep Learning: Beginner to Advanced": [
        "Welcome to Our Deep Learning Experience",
        "Getting Started",
        "Neural Networks: Fundamentals",
        "Getting Started with PyTorch",
        "Neural Networks: Training",
        "Neural Networks in PyTorch",
        "Model Optimization: Training Algorithms",
        "Model Optimization: Regularization Techniques",
        "Model Optimization: Hyperparameter Tunning",  # DB has typo
        "Convolutional Neural Networks (CNN)",
        "Sequence Models",
        "Transformers",
        "Project: Car Damage Detection",
        "Final Quiz",
        "Deep Learning Interview Question Bank",
        "What's Next",
    ],
    "Gen AI": [
        "Welcome to the Gen AI Experience",
        "Introduction to Generative AI",
        "Gen AI Essential Concepts",
        "Theoretical Fundamentals",
        "LangChain & Prompting Essentials",
        "Vector Database",
        "Project 1: Real Estate Assistant Using RAG",
        "Project 2: E-Commerce Chatbot",
        "Agentic AI: A Hands-on Approach",
        "AI Agents",
        "Agentic AI: Architecture and Protocols",
        "Agentic AI: Building Multi-Agent Systems",
        "Agentic AI: Evaluation for Safety and Task Success",
        "Agentic AI: Business Project 3",
        "Fine-Tuning",
        "Ethics in Gen AI",
        "LangGraph Crash Course",
        "Crew AI Crash Course",
        "Final Quiz",
        "Gen AI Interview Question Bank",
        "What's Next",
    ],
    "Math and Statistics For AI, Data Science": [
        "Welcome to Math and Statistics Experience",
        "Data & Visualization Basics",
        "Measures Of Central Tendency and Dispersion",
        "Probability Theory",
        "Distributions",
        "AtliQo Bank Project",
        "Phase 1: Find Target Market",
        "Central Limit Theorem",
        "Hypothesis Testing",
        "Phase 2: A/B Testing For New Credit Card",
        "Advanced Hypothesis Testing (Bonus Section)",
        "Final QuizMandatory",
        "What's Next?",
    ],
    "Python: Beginner to Advanced For Data Professionals": [
        "Welcome to the Python Experience",
        "Project Description",
        "Python Basics: Getting Started",
        "Python Basics: Variables, Numbers and Strings",
        "Python Basics: Lists, If Condition and For Loop",
        "Python Basics: Functions, Dictionaries, Tuples and File Handling",
        "Python Basics: Classes and Exception Handling",
        "Python Basics: NumPy",
        "Python Basics: EDA Using Pandas, Matplotlib and Seaborn",
        "Project 1: Exploratory Data Analytics (EDA) in Hospitality Domain",
        "Python Advanced: Comprehensions and Sets",
        "Python Advanced: JSON, Generators and Decorators",
        "Python Advanced: APIs",
        "Python Advanced: Logging, Pytest, Pydantic and Databases",
        "Project 2: Expense Tracking System",
        "Final Quiz",
        "Python Interview Question Bank",
        "What's Next",
    ],
    "SQL Beginner to Advanced For Data Professionals": [
        "Welcome to The SQL Experience",
        "SQL Basics: Data Retrieval - Single Table",
        "SQL Basics: Data Retrieval - Multiple Tables",
        "SQL Basics: Complex Queries",
        "SQL Basics: Database Creation & Updates",
        "AtliQ Hardware & Problem Statement",
        "SQL Advanced: Finance Analytics",
        "SQL Advanced: Top Customers, Products, Markets",
        "SQL Advanced: Supply Chain Analytics",
        "Final Quiz",
        "What's Next?",
    ],
    "Virtual Internship": [
        "Unlock Discord Channels",
        "Week 1",
        "Week1",
        "Week 2",
        "Week 3 & 4",
        "Our Relationship After You Land a Job",
        "What's Next?",
    ],
    "Welcome to The Gen AI and Data Science Bootcamp Experience": [
        "Welcome to the Bootcamp Experience",
        "What is Build In Public?",
        "Enhance Your Learning Experience",
        "What's Next",
    ],
    "Mastering Communication & Stakeholder Management": [
        "Welcome to the Mastering Communication & Stakeholder Management Experience",
        "Communication Maturity Assessment",
        "Basics: For Effective Communication",
        "Solving Common Communication Hurdles: Early Career",
        "Solving Common Communication Hurdles: Mid-level - Advanced",
        "Mastering Multi Channel Communication at Work",
        "Stakeholder Mapping & Career Success",
        "Communication Frameworks with Real Business Scenarios",
        "Action: Build Your Personal Communication Improvement Tracker",
        "More Practice Scenarios",
        "Burning Questions",
        "Course Completion Test",
    ],
    "Mastering Time Management & Deep Work": [
        'Welcome to "Mastering the Time Management" Experience',
        "Time Management Maturity Assessment",
        "Foundation: Effective Time Management",
        "Solving Common Time Management Hurdles: Beginner",
        "Solving Common Time Management Hurdles: Mid to Advanced Stage",
        "Mastering Time Through Habits",
        "Strategic Time Management Frameworks",
        "Creating Your Deep Work System",
        "Action: Build Your Personal Time Mgmt. Improvement Tracker",
        "Simulation Lab: More Practice Scenarios",
        "Burning Questions",
        "Course Completion Test",
    ],
    "Building Online Credibility, Portfolio Projects & ATS Resume": [
        "Unlock Discord Channels",
        "Build Your Resume, Now!",
        "Codebasics - Resume Builder Tool",
        "Job Winning Resumes",
        "Power BI Project(s) for Your Portfolio!",
        "Let's Create Your Portfolio Website",
        "Online Credibility",
        "Smart Job Assistance Portal!",
        "Practicing Domain Knowledge",
        "What's Next?",
    ],
    "Interview Preparation / Job Assistance": [
        "Get Prepared For Interview, Now!",
        "The Ultimate Interview Playbook",
        "Data Analyst Mock Interviews",
        "Codebasics - Mock Interview Portal",
        "Interview Questions",
        "Interview Coaching Live Session",
        "Our Relationship After You Land a Job",
        "What's Next?",
    ],
    "Online Credibility": [
        "Unlock Discord Channels",
        "Introduction to online credibility / open-source contribution",
        "Get Your LinkedIn Profile Right",
        "Python Projects for Your Portfolio!",
        "Introduction to Online Credibility",
        "Python & SQL project(s) for your Portfolio",
        "What's Next?",
    ],
    "SQL for Data Science": [
        "Welcome to The SQL Experience",
        "SQL Basics: Data Retrieval - Single Table",
        "SQL Basics: Data Retrieval - Multiple Tables",
        "Final Quiz",
        "What's Next?",
    ],
    "Job Assistance Portal, ATS Resume & Portfolio Website": [
        "Job Assistance Portal (JAP)",
        "Build Your ATS Resume, Now!",
        "Let's Create Your Portfolio Website",
        "Online Credibility",
        "What's Next",
    ],
}


def get_chapter_override(course_title: str) -> Optional[List[str]]:
    """Return the correct chapter order for a course, or None if no override."""
    return CHAPTER_OVERRIDES.get(course_title)


# ---- Keyword fallback for courses not in the catalog ----
_KEYWORD_RULES = [
    (["power bi", "excel", "sql", "tableau", "fabric", "da 2.0"],   DATA_ANALYTICS),
    (["python"],                                                     PROGRAMMING),
    (["machine learning", "deep learning", "math and statistics",
      "nlp", "natural language"],                                    AI_DATA_SCIENCE),
    (["ai automation", "gen ai", "ai toolkit", "agentic"],           AI_AUTOMATION),
    (["data engineering", "spark", "snowflake", "airflow",
      "kafka", "flink", "etl"],                                      DATA_ENGINEERING),
    (["communication", "time management", "personal branding"],      SOFT_SKILLS),
    (["project", "case stud"],                                       PROJECTS),
    (["interview", "job", "credibility", "resume",
      "internship", "applying"],                                     CAREER),
    (["welcome", "bootcamp experience"],                             WELCOME),
    (["webinar", "live", "problem-solving session"],                 LIVE_SESSIONS),
]


def get_course_metadata(course_title: str) -> str:
    """Return the category for a course title.

    Exact-match lookup first, then keyword fallback.
    Returns "Course" as a safe default if nothing matches.
    """
    # Exact match
    if course_title in COURSE_CATALOG:
        return COURSE_CATALOG[course_title]

    # Keyword fallback
    lower = course_title.lower()
    for keywords, category in _KEYWORD_RULES:
        if any(kw in lower for kw in keywords):
            return category

    return "Course"
