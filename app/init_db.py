"""
Database initialization script with default sources and categories
"""
import asyncio
from sqlalchemy import select
from app.database import AsyncSessionLocal, init_db
from app.models import Source, Category


# Default categories
DEFAULT_CATEGORIES = [
    {"name": "World", "description": "International news and global affairs"},
    {"name": "Politics", "description": "Political news and government affairs"},
    {"name": "Business", "description": "Business, finance, and economic news"},
    {"name": "Technology", "description": "Technology and innovation news"},
    {"name": "Science", "description": "Scientific discoveries and research"},
    {"name": "Culture", "description": "Arts, culture, and entertainment"},
    {"name": "Humanitarian", "description": "Humanitarian crises and aid"},
    {"name": "Environment", "description": "Climate and environmental news"},
]

# Diverse global news sources - prioritizing non-Western perspectives
# Philosophy: Break the Western-centric content bubble by prioritizing Global South,
# non-Western regions, independent outlets, and alternative perspectives
DEFAULT_SOURCES = [
    # Middle East & North Africa (MENA)
    {
        "name": "Al Jazeera",
        "url": "https://www.aljazeera.com",
        "rss_url": "https://www.aljazeera.com/xml/rss/all.xml",
        "region": "MENA",
        "language": "en",
        "bias_indicator": "Center-Left",
        "description": "Qatar-based international news network with Arab perspective"
    },
    {
        "name": "Haaretz",
        "url": "https://www.haaretz.com",
        "rss_url": "https://www.haaretz.com/cmlink/1.1617539",
        "region": "MENA",
        "language": "en",
        "bias_indicator": "Center-Left",
        "description": "Israeli liberal newspaper with English edition"
    },
    {
        "name": "Middle East Eye",
        "url": "https://www.middleeasteye.net",
        "rss_url": "https://www.middleeasteye.net/rss",
        "region": "MENA",
        "language": "en",
        "bias_indicator": "Center",
        "description": "Independent news agency focused on Middle East"
    },
    
    # Asia & Pacific
    {
        "name": "South China Morning Post",
        "url": "https://www.scmp.com",
        "rss_url": "https://www.scmp.com/rss/91/feed",
        "region": "Asia",
        "language": "en",
        "bias_indicator": "Center",
        "description": "Hong Kong-based English language newspaper"
    },
    {
        "name": "Kyodo News",
        "url": "https://english.kyodonews.net",
        "rss_url": "https://english.kyodonews.net/rss/news.xml",
        "region": "Asia",
        "language": "en",
        "bias_indicator": "Center",
        "description": "Japan's leading news agency"
    },
    {
        "name": "The Wire",
        "url": "https://thewire.in",
        "rss_url": "https://thewire.in/rss",
        "region": "Asia",
        "language": "en",
        "bias_indicator": "Center-Left",
        "description": "Independent Indian investigative journalism"
    },
    {
        "name": "The Diplomat",
        "url": "https://thediplomat.com",
        "rss_url": "https://thediplomat.com/feed",
        "region": "Asia",
        "language": "en",
        "bias_indicator": "Center",
        "description": "Magazine covering Asia-Pacific politics and culture"
    },
    
    # Africa
    {
        "name": "Mail & Guardian",
        "url": "https://mg.co.za",
        "rss_url": "https://mg.co.za/rss",
        "region": "Africa",
        "language": "en",
        "bias_indicator": "Center-Left",
        "description": "South African investigative journalism"
    },
    {
        "name": "The Africa Report",
        "url": "https://www.theafricareport.com",
        "rss_url": "https://www.theafricareport.com/feed/",
        "region": "Africa",
        "language": "en",
        "bias_indicator": "Center",
        "description": "Business and politics across Africa"
    },
    {
        "name": "African Arguments",
        "url": "https://africanarguments.org",
        "rss_url": "https://africanarguments.org/feed/",
        "region": "Africa",
        "language": "en",
        "bias_indicator": "Center",
        "description": "Pan-African platform for debate and analysis"
    },
    
    # Latin America
    {
        "name": "Americas Quarterly",
        "url": "https://americasquarterly.org",
        "rss_url": "https://americasquarterly.org/feed/",
        "region": "Americas",
        "language": "en",
        "bias_indicator": "Center",
        "description": "Politics and business in the Americas"
    },
    {
        "name": "Buenos Aires Times",
        "url": "https://www.batimes.com.ar",
        "rss_url": "https://www.batimes.com.ar/feed/",
        "region": "Americas",
        "language": "en",
        "bias_indicator": "Center",
        "description": "English news from Argentina"
    },
    
    # International & Global
    {
        "name": "Inter Press Service",
        "url": "https://www.ipsnews.net",
        "rss_url": "https://www.ipsnews.net/news/feed/",
        "region": "International",
        "language": "en",
        "bias_indicator": "Center-Left",
        "description": "News agency focusing on developing nations"
    },
    {
        "name": "Global Voices",
        "url": "https://globalvoices.org",
        "rss_url": "https://globalvoices.org/feed",
        "region": "International",
        "language": "en",
        "bias_indicator": "Center",
        "description": "Citizen media from around the world"
    },
    
    # Global Baseline Sources
    {
        "name": "Reuters",
        "url": "https://www.reuters.com",
        "rss_url": "https://www.reutersagency.com/feed/?taxonomy=markets&post_type=reuters-best",
        "region": "International",
        "language": "en",
        "bias_indicator": "Center",
        "description": "International news agency, baseline for comparison"
    },
    {
        "name": "Deutsche Welle",
        "url": "https://www.dw.com",
        "rss_url": "https://rss.dw.com/rdf/rss-en-all",
        "region": "Europe",
        "language": "en",
        "bias_indicator": "Center",
        "description": "German public international broadcaster"
    },
    
    # Additional Independent Sources - Global South & Alternative Perspectives
    {
        "name": "Pambazuka News",
        "url": "https://www.pambazuka.org",
        "rss_url": "https://www.pambazuka.org/rss.xml",
        "region": "Africa",
        "language": "en",
        "bias_indicator": "Center-Left",
        "description": "Pan-African news platform on governance and citizenship"
    },
    {
        "name": "Asia Sentinel",
        "url": "https://www.asiasentinel.com",
        "rss_url": "https://www.asiasentinel.com/feed/",
        "region": "Asia",
        "language": "en",
        "bias_indicator": "Center",
        "description": "Independent news on Asia from journalists in the region"
    },
    {
        "name": "Dawn",
        "url": "https://www.dawn.com",
        "rss_url": "https://www.dawn.com/feed",
        "region": "Asia",
        "language": "en",
        "bias_indicator": "Center",
        "description": "Pakistan's oldest English-language newspaper"
    },
    {
        "name": "Telesur English",
        "url": "https://www.telesurenglish.net",
        "rss_url": "https://www.telesurenglish.net/rss.xml",
        "region": "Americas",
        "language": "en",
        "bias_indicator": "Left",
        "description": "Latin American multi-state news network"
    },
    {
        "name": "The Guardian Nigeria",
        "url": "https://guardian.ng",
        "rss_url": "https://guardian.ng/feed/",
        "region": "Africa",
        "language": "en",
        "bias_indicator": "Center",
        "description": "Leading Nigerian newspaper"
    },
    {
        "name": "Jakarta Post",
        "url": "https://www.thejakartapost.com",
        "rss_url": "https://www.thejakartapost.com/rss",
        "region": "Asia",
        "language": "en",
        "bias_indicator": "Center",
        "description": "English-language Indonesian newspaper"
    },
    {
        "name": "Equal Times",
        "url": "https://www.equaltimes.org",
        "rss_url": "https://www.equaltimes.org/rss",
        "region": "International",
        "language": "en",
        "bias_indicator": "Left",
        "description": "Independent trade union news agency"
    },
    {
        "name": "Jacobin",
        "url": "https://jacobin.com",
        "rss_url": "https://jacobin.com/feed",
        "region": "International",
        "language": "en",
        "bias_indicator": "Left",
        "description": "Magazine of socialist analysis"
    },
    {
        "name": "The Bullet",
        "url": "https://socialistproject.ca/bullet",
        "rss_url": "https://socialistproject.ca/bullet/rss.xml",
        "region": "International",
        "language": "en",
        "bias_indicator": "Left",
        "description": "Canadian socialist news and analysis"
    },
    
    # NEW SOURCES - Additional Global South & Alternative Perspectives (2024-2025)
    
    # Africa - Additional sources
    {
        "name": "AllAfrica",
        "url": "https://allafrica.com",
        "rss_url": "https://allafrica.com/tools/headlines/rss/allafrica.xml",
        "region": "Africa",
        "language": "en",
        "bias_indicator": "Center",
        "description": "Pan-African news platform aggregating stories from African publishers"
    },
    {
        "name": "Africanews",
        "url": "https://www.africanews.com",
        "rss_url": "https://www.africanews.com/feed/",
        "region": "Africa",
        "language": "en",
        "bias_indicator": "Center",
        "description": "Pan-African news channel based in Congo, providing African perspectives"
    },
    
    # Asia - Additional sources
    {
        "name": "Nikkei Asia",
        "url": "https://asia.nikkei.com",
        "rss_url": "https://asia.nikkei.com/Rss/RssFeed?nodeId=5001",
        "region": "Asia",
        "language": "en",
        "bias_indicator": "Center",
        "description": "Business and politics news from Asia, with focus on Japan and East Asia"
    },
    {
        "name": "BenarNews",
        "url": "https://www.benarnews.org",
        "rss_url": "https://www.benarnews.org/rss/english/rss.xml",
        "region": "Asia",
        "language": "en",
        "bias_indicator": "Center",
        "description": "Independent news service focusing on Asia, part of RFA"
    },
    
    # MENA - Additional sources
    {
        "name": "Al-Monitor",
        "url": "https://www.al-monitor.com",
        "rss_url": "https://www.al-monitor.com/rss.xml",
        "region": "MENA",
        "language": "en",
        "bias_indicator": "Center",
        "description": "Middle East news and analysis from local journalists"
    },
    
    # Latin America - Additional sources
    {
        "name": "Nicaragua Dispatch",
        "url": "https://nicaraguadispatch.com",
        "rss_url": "https://nicaraguadispatch.com/feed/",
        "region": "Americas",
        "language": "en",
        "bias_indicator": "Center",
        "description": "Independent news on Nicaragua and Central America"
    },
    
    # International/Alternative - Additional sources
    {
        "name": "Peoples Dispatch",
        "url": "https://peoplesdispatch.org",
        "rss_url": "https://rss.peoplesdispatch.org/",
        "region": "International",
        "language": "en",
        "bias_indicator": "Left",
        "description": "International media covering people's movements and Global South perspectives"
    },
    {
        "name": "The New Humanitarian",
        "url": "https://www.thenewhumanitarian.org",
        "rss_url": "https://www.thenewhumanitarian.org/rss/all.xml",
        "region": "International",
        "language": "en",
        "bias_indicator": "Center",
        "description": "Independent humanitarian news covering crises worldwide"
    },
    {
        "name": "ZNetwork",
        "url": "https://znetwork.org",
        "rss_url": "https://znetwork.org/feed/",
        "region": "International",
        "language": "en",
        "bias_indicator": "Left",
        "description": "Progressive media network covering global justice and anti-imperialism"
    },
    {
        "name": "Countercurrents",
        "url": "https://countercurrents.org",
        "rss_url": "https://countercurrents.org/feed/",
        "region": "International",
        "language": "en",
        "bias_indicator": "Left",
        "description": "Independent news on peace, justice and anti-imperialism"
    },
    {
        "name": "Truthout",
        "url": "https://truthout.org",
        "rss_url": "https://truthout.org/feed/",
        "region": "International",
        "language": "en",
        "bias_indicator": "Left",
        "description": "Independent progressive news on social justice and democracy"
    },
    {
        "name": "Common Dreams",
        "url": "https://www.commondreams.org",
        "rss_url": "https://www.commondreams.org/rss.xml",
        "region": "International",
        "language": "en",
        "bias_indicator": "Left",
        "description": "Progressive news on peace, justice and sustainability"
    },
]


async def seed_categories(session):
    """Seed default categories"""
    for cat_data in DEFAULT_CATEGORIES:
        # Check if category already exists
        result = await session.execute(
            select(Category).where(Category.name == cat_data["name"])
        )
        if result.scalar_one_or_none() is None:
            category = Category(**cat_data)
            session.add(category)
            print(f"Added category: {cat_data['name']}")
    await session.commit()


async def seed_sources(session):
    """Seed default news sources"""
    for src_data in DEFAULT_SOURCES:
        # Check if source already exists
        result = await session.execute(
            select(Source).where(Source.rss_url == src_data["rss_url"])
        )
        if result.scalar_one_or_none() is None:
            source = Source(**src_data)
            session.add(source)
            print(f"Added source: {src_data['name']} ({src_data['region']})")
    await session.commit()


async def main():
    """Main initialization function"""
    print("Initializing database...")
    
    # Create tables
    await init_db()
    print("Database tables created.")
    
    # Seed data
    async with AsyncSessionLocal() as session:
        print("\nSeeding categories...")
        await seed_categories(session)
        
        print("\nSeeding sources...")
        await seed_sources(session)
    
    print("\nDatabase initialization complete!")


if __name__ == "__main__":
    asyncio.run(main())
