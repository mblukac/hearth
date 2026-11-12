"""The authored starting world and the engine's executable action vocabulary.

All residents are fictional adults. Intimacy is an abstract relationship event,
and family simulation deliberately contains no explicit sexual material.
"""

from copy import deepcopy

MAP_WIDTH, MAP_HEIGHT = 48, 34


def location(key, name, kind, x, y, w, h, color):
    return dict(id=key, name=name, type=kind, x=x, y=y, w=w, h=h,
                color=color, entrance={"x": x + w // 2, "y": min(33, y + h)})


LOCATIONS = [
    location("farm", "Willow fields", "farm", 3, 3, 7, 5, "#c8b36e"),
    location("workshop", "The anvil & wheel", "workshop", 14, 3, 5, 4, "#849789"),
    location("bakery", "Morning loaf", "bakery", 22, 3, 5, 4, "#ca976e"),
    location("clinic", "Juniper clinic", "clinic", 32, 3, 5, 4, "#d5d1a5"),
    location("tavern", "The Wandering Hare", "tavern", 4, 12, 6, 5, "#bb8771"),
    location("town_hall", "Assembly house", "civic", 15, 12, 6, 5, "#a9a2b4"),
    location("market", "Market exchange", "market", 26, 11, 6, 5, "#d1b36b"),
    location("school", "The learning room", "school", 35, 12, 5, 4, "#90aa98"),
    # Homes sit inside the lane grid drawn in static/scene.js: one per block in the
    # two western columns, two per block in the wide eastern column.
    location("home_1", "Orchard cottage", "home", 4, 22, 5, 4, "#aba58b"),
    location("home_2", "The blue door", "home", 15, 22, 5, 4, "#859b9e"),
    location("home_3", "Rosemary house", "home", 26, 22, 5, 4, "#b8a690"),
    location("home_4", "Maple rooms", "home", 26, 29, 5, 3, "#bd9990"),
    location("home_5", "The old millhouse", "home", 4, 29, 5, 3, "#9aa481"),
    location("home_6", "Weavers' courtyard", "home", 15, 29, 5, 3, "#b799ab"),
    location("home_7", "Little green house", "home", 34, 22, 5, 4, "#87a88a"),
    location("home_8", "Riverside lodge", "home", 34, 29, 5, 3, "#a3957c"),
    location("pond", "Stillwater pond", "water", 38, 2, 4, 3, "#769fba"),
    location("river", "The Silverwater", "water", 44, 0, 4, 34, "#628eaa"),
]


# Name, age, gender, pronouns, job, home, workplace, color, skin, hair,
# identity, education, financial background, backstory, goal, values, traits,
# reproductive capacity, orientation.
PERSONAS = [
    ("Mara Vale", 34, "woman", "she/her", "farmer", "home_1", "farm", "#c48055", "#bd8965", "#51392e",
     "Hearth-born; river-valley heritage", "agricultural apprenticeship", "land-poor smallholder",
     "Mara inherited a tired orchard and her mother's habit of feeding whoever turns up. Two bad harvests taught her thrift; her childhood friend Ivo still gets the last apple.",
     "Make the orchard resilient enough to start a family without fearing winter.", ["stewardship", "family", "fairness"],
     [61, 86, 46, 81, 42], "can_gestate", "bisexual"),
    ("Ivo Chen", 36, "man", "he/him", "carpenter", "home_1", "workshop", "#6b938b", "#cba47c", "#282a29",
     "Second-generation valley resident; Chinese diaspora heritage", "carpentry guild training", "steady craft income",
     "Ivo arrived as a child and learned the village by repairing its doors. His quiet partnership with Mara is strong, though he worries his work leaves no room for parenthood.",
     "Build a larger workshop and protect evenings with Mara.", ["craft", "loyalty", "patience"],
     [70, 83, 35, 79, 37], "can_contribute_sperm", "heterosexual"),
    ("Leila Haddad", 29, "woman", "she/her", "physician", "home_2", "clinic", "#caa35d", "#b8815d", "#312b2c",
     "Coastal migrant; Arab heritage", "university medicine", "modest professional income",
     "Leila left a crowded coastal hospital to reopen Hearth's clinic. She is capable in emergencies and awkward at accepting help, and misses the sounds of her old neighborhood.",
     "Create a clinic that treats everyone and find people she can rely on.", ["care", "evidence", "independence"],
     [84, 88, 49, 85, 52], "can_gestate", "bisexual"),
    ("Tomás Rivera", 31, "man", "he/him", "baker", "home_3", "bakery", "#b87065", "#b77852", "#30241f",
     "Valley-born; Latin American diaspora heritage", "family bakery apprenticeship", "small business owner",
     "Tomás measures affection in warm bread. A failed engagement made him slower to trust promises, but never quieter at the market. He is secretly practicing music after closing.",
     "Keep the bakery solvent and be known for something beyond his bread.", ["hospitality", "humor", "art"],
     [76, 67, 90, 82, 41], "can_contribute_sperm", "bisexual"),
    ("Edda Holm", 58, "woman", "she/her", "mayor", "home_4", "town_hall", "#8e82b4", "#ddbb98", "#bab6a8",
     "Third-generation Hearth resident; Nordic heritage", "public administration certificate", "comfortable but frugal",
     "Edda once organized a flood rescue and has led the assembly ever since. She believes compromise holds the village together; younger residents increasingly call it delay.",
     "Leave Hearth with sound public finances and an orderly succession.", ["stability", "duty", "reputation"],
     [46, 92, 67, 57, 50], "none", "heterosexual"),
    ("Soren Holm", 60, "man", "he/him", "fisher", "home_4", "market", "#728f9c", "#cea987", "#b1b1a1",
     "Lakeshore-born; Nordic heritage", "secondary school", "variable fishing income",
     "Soren married Edda before either imagined public life. He reads the weather more readily than a room and quietly gives fish to neighbors whose cupboards look empty.",
     "Restore the river habitat and persuade Edda to take a day off.", ["nature", "generosity", "privacy"],
     [61, 71, 28, 88, 33], "can_contribute_sperm", "heterosexual"),
    ("Amina Okafor", 42, "woman", "she/her", "teacher", "home_5", "school", "#bd9b52", "#77503c", "#27231f",
     "New Hearth resident; West African diaspora heritage", "university education", "stable public salary",
     "Amina moved here after years teaching in a large city. She treats disagreement as a skill people can learn, but her older brother Kwame says she works too hard at fixing everyone.",
     "Turn the school into a place where every generation can learn.", ["learning", "dignity", "community"],
     [88, 81, 65, 90, 35], "can_gestate", "heterosexual"),
    ("Kwame Okafor", 45, "man", "he/him", "smith", "home_5", "workshop", "#a56e50", "#704b38", "#242422",
     "New Hearth resident; West African diaspora heritage", "metalworking apprenticeship", "debt-financed workshop share",
     "Kwame followed his sister Amina to Hearth after a factory closure. He is proud of his tools, impatient with bureaucracy, and determined never to be disposable labor again.",
     "Own his workshop outright and win a fair voice for workers.", ["solidarity", "skill", "justice"],
     [60, 79, 72, 53, 59], "can_contribute_sperm", "heterosexual"),
    ("Jun Park", 24, "nonbinary", "they/them", "courier", "home_6", "market", "#8da758", "#d5b292", "#313230",
     "Hearth-born; Korean diaspora heritage", "secondary school and self-study", "precarious casual income",
     "Jun knows every shortcut and almost every secret because everyone forgets the courier is listening. They want to travel, but their friendship with Nell makes leaving complicated.",
     "Save enough to travel while finding a place to belong.", ["freedom", "friendship", "curiosity"],
     [94, 48, 83, 73, 55], "none", "pansexual"),
    ("Nell Brooks", 25, "woman", "she/her", "weaver", "home_6", "workshop", "#b57d9b", "#d8af8d", "#916947",
     "Hearth-born; mixed valley heritage", "textile apprenticeship", "irregular commission income",
     "Nell turns discarded cloth into beautiful work. Her father's long illness taught her to notice fatigue in others; she hides her own anxiety behind elaborate jokes.",
     "Sell her designs beyond the valley without losing her friendships.", ["creativity", "kindness", "belonging"],
     [93, 66, 59, 87, 69], "can_gestate", "pansexual"),
    ("Pavel Novak", 39, "man", "he/him", "miller", "home_7", "farm", "#a28f65", "#c49f7f", "#544132",
     "Mountain migrant; Central European heritage", "technical secondary school", "small mortgage and stable wages",
     "Pavel rebuilt the mill's machinery after arriving with one suitcase. He trusts maintenance schedules more than speeches and is raising money to bring his aging parents closer.",
     "Make the village food supply reliable and build a family of his own.", ["reliability", "family", "honesty"],
     [48, 95, 32, 67, 48], "can_contribute_sperm", "heterosexual"),
    ("Rosa Almeida", 38, "woman", "she/her", "innkeeper", "home_7", "tavern", "#c98075", "#b78665", "#50342c",
     "Coastal-born; Lusophone heritage", "hospitality diploma", "business income with seasonal debt",
     "Rosa bought the tavern after a divorce and built a reputation for remembering everybody's birthday. Her relationship with Pavel is tender, but she refuses to disappear into anyone else's plans.",
     "Keep the tavern a safe gathering place and choose her next chapter freely.", ["autonomy", "welcome", "candor"],
     [76, 76, 92, 80, 39], "can_gestate", "bisexual"),
    ("Dev Shah", 27, "man", "he/him", "merchant", "home_8", "market", "#7898b2", "#986b49", "#27252a",
     "Regional migrant; South Asian heritage", "business college", "aspiring middle income, leveraged stock",
     "Dev arrived with a cart, a ledger and more confidence than money. He wants to modernize trade, but remembers how his mother's shop failed when everyone stopped trusting credit.",
     "Build a trading cooperative that earns both money and trust.", ["enterprise", "reciprocity", "progress"],
     [85, 73, 89, 60, 57], "can_contribute_sperm", "gay"),
    ("Felix Moreau", 28, "man", "he/him", "musician", "home_8", "tavern", "#9f83be", "#d1a78c", "#463a30",
     "City migrant; Francophone heritage", "conservatory, unfinished", "insecure gig income",
     "Felix left the conservatory after burnout and now plays for supper as often as wages. He is falling for Dev, whose spreadsheets feel unexpectedly reassuring.",
     "Write a song worth staying for and earn a dependable living.", ["beauty", "sincerity", "intimacy"],
     [96, 40, 75, 80, 64], "can_contribute_sperm", "gay"),
    ("Ada Finch", 67, "woman", "she/her", "herbalist", "home_2", "clinic", "#94a06e", "#bd9276", "#d1c9b6",
     "Lifelong valley resident; local heritage", "community herbal apprenticeship", "small pension and barter",
     "Ada knows the hillside plants and three generations of village arguments. Widowed six years ago, she resents being treated as fragile and has become Leila's exacting ally.",
     "Pass on useful knowledge without letting nostalgia overrule evidence.", ["wisdom", "self-reliance", "care"],
     [80, 78, 58, 75, 38], "none", "bisexual"),
    ("Bram Reed", 52, "man", "he/him", "warden", "home_3", "town_hall", "#7d8870", "#ab8060", "#72695c",
     "Border-town migrant; regional heritage", "public safety training", "modest public salary",
     "Bram once enforced rules too rigidly and still regrets a family he failed to help. Hearth gives him a chance to keep people safe by listening before reaching for authority.",
     "Earn trust as a protector and repair his relationship with uncertainty.", ["safety", "restraint", "accountability"],
     [48, 86, 43, 70, 63], "can_contribute_sperm", "heterosexual"),
    ("Tess Morgan", 22, "woman", "she/her", "farmhand", "home_6", "farm", "#c68e4e", "#d8b48c", "#b07441",
     "Hearth-born; valley heritage", "secondary school", "low hourly wages",
     "Tess works the fields and reads political pamphlets under the orchard trees. She loves the village fiercely and is tired of being told to wait her turn.",
     "Win affordable housing and a binding vote for younger workers.", ["equality", "courage", "solidarity"],
     [89, 60, 84, 63, 54], "can_gestate", "lesbian"),
    ("Yara Silva", 26, "woman", "she/her", "gardener", "home_5", "farm", "#75a386", "#a87151", "#2b2925",
     "Recent valley migrant; Brazilian heritage", "horticulture diploma", "modest seasonal income",
     "Yara came to restore the communal gardens after a wildfire displaced her family. She can calm a frightened animal, but thunder still makes her reach for her bag.",
     "Create a home that feels permanent and help the village prepare for disasters.", ["ecology", "security", "affection"],
     [83, 78, 54, 89, 65], "can_gestate", "lesbian"),
    ("Owen Price", 47, "man", "he/him", "accountant", "home_4", "town_hall", "#828f9a", "#d0ae8a", "#6d6255",
     "Regional town migrant; Welsh heritage", "accounting qualification", "comfortable salaried income",
     "Owen came to untangle the village accounts and stayed after people began inviting him to supper. Numbers feel safer than people, though his dry humor has started to escape.",
     "Make public spending understandable enough that nobody needs blind trust.", ["transparency", "order", "fairness"],
     [56, 96, 25, 65, 57], "can_contribute_sperm", "asexual"),
    ("Sana Rahman", 33, "woman", "she/her", "librarian", "home_2", "school", "#ac879c", "#aa7c59", "#30292b",
     "City migrant; Bengali heritage", "library science degree", "modest public salary",
     "Sana built a traveling library before taking the room beside Amina's school. She believes stories can make strangers legible, but is careful about which parts of her own story she shares.",
     "Record Hearth's many histories and allow herself to form lasting attachments.", ["truth", "pluralism", "tenderness"],
     [94, 80, 40, 88, 49], "can_gestate", "bisexual"),
]


def initial_villagers(rng):
    villagers = []
    positions = [(8, 9), (12, 9), (33, 8), (24, 8), (18, 18), (30, 18),
                 (37, 17), (16, 8), (29, 18), (13, 19), (10, 10), (8, 18),
                 (28, 17), (10, 19), (35, 9), (20, 19), (6, 10), (8, 11),
                 (21, 18), (34, 17)]
    for index, row in enumerate(PERSONAS):
        (name, age, gender, pronouns, occupation, home, workplace, color, skin, hair,
         identity, education, finances, backstory, goal, values, traits, capacity, orientation) = row
        villager_id = f"v{index + 1:02d}"
        villagers.append(dict(
            id=villager_id, name=name, age=age, gender=gender, pronouns=pronouns,
            occupation=occupation, home=home, workplace=workplace, color=color, skin=skin, hair=hair,
            backstory=backstory, goal=goal, values=values,
            traits=dict(zip(("openness", "conscientiousness", "extraversion", "agreeableness", "neuroticism"), traits)),
            demographics=dict(identity=identity, education=education, economic_background=finances,
                              languages=["Common", "regional dialect"], orientation=orientation,
                              reproductive_capacity=capacity, relationship_preference="monogamous",
                              intimacy_preference="declines" if orientation == "asexual" else "conditional on mutual consent",
                              religion="personal / not specified", disability="none specified",
                              residence_years=min(age - 18, 2 + index % 15)),
            x=positions[index][0], y=positions[index][1], action="idle", action_label="Taking in the morning",
            target_id=None, destination=None, pending_action=None,
            needs=dict(energy=rng.randint(66, 94), hunger=rng.randint(60, 88),
                       social=rng.randint(45, 83), safety=rng.randint(65, 94)),
            mood="hopeful" if index % 3 == 0 else "content", wallet=rng.randint(12, 60),
            thought=f"{goal} I wonder what this morning will bring.", speech="",
            relationships={}, memories=[], decision=None, cooldowns={},
            family={"parents": [], "children": [], "siblings": []}, pregnancy=None,
            birth_day=1 - age * 365, last_action_at=-100,
        ))
    for actor in villagers:
        for other in villagers:
            if actor is other:
                continue
            affinity = rng.randint(5, 30)
            trust = rng.randint(10, 35)
            if actor["home"] == other["home"]:
                affinity += 15
                trust += 15
            actor["relationships"][other["id"]] = dict(affinity=affinity, trust=trust, romance=0, status="neighbor")
    for first, second, affinity, trust, romance, status in [
        (0, 1, 86, 90, 82, "partner"), (4, 5, 86, 93, 75, "married"),
        (10, 11, 72, 76, 62, "partner"), (12, 13, 55, 54, 41, "crush"),
        (8, 9, 67, 65, 32, "crush"), (16, 17, 51, 48, 26, "crush"),
        (2, 14, 71, 74, 0, "friend"), (6, 19, 68, 74, 0, "friend"),
        (6, 7, 80, 88, 0, "family"), (3, 11, 54, 68, 0, "friend"),
    ]:
        for a, b in ((villagers[first], villagers[second]), (villagers[second], villagers[first])):
            a["relationships"][b["id"]] = dict(affinity=affinity, trust=trust, romance=romance, status=status)
            if status in ("partner", "married"):
                a["partner_id"] = b["id"]
    villagers[6]["family"]["siblings"] = [villagers[7]["id"]]
    villagers[7]["family"]["siblings"] = [villagers[6]["id"]]
    return villagers


def action(key, label, category, description, *, target=False, location=None,
           needs=None, bond=None, world=None, cost=0, income=0, cooldown=20, **extra):
    return dict(id=key, label=label, category=category, description=description,
                requires_target=target, location=location, needs=needs or {},
                bond=bond or {}, world=world or {}, cost=cost, income=income,
                cooldown=cooldown, **extra)


ACTIONS = [
    action("eat", "Eat a meal", "needs", "Take a meal from the shared food supply.", location="market", needs={"hunger": 45, "energy": 4}, world={"food": -1}, cooldown=90),
    action("cook", "Cook supper", "needs", "Prepare a filling meal at home.", location="home", needs={"hunger": 52, "energy": -3}, world={"food": -1}, cooldown=100),
    action("sleep", "Sleep", "needs", "Sleep safely at home to restore energy.", location="home", needs={"energy": 75, "safety": 4}, cooldown=240, duration=120),
    action("rest", "Take a breather", "needs", "Rest quietly and recover energy.", needs={"energy": 25, "safety": 2}, cooldown=40),
    action("wash", "Wash up", "needs", "Freshen up at home and feel more settled.", location="home", needs={"energy": 6, "safety": 5}, cooldown=120),
    action("go_home", "Return home", "movement", "Walk home and feel grounded.", location="home", needs={"safety": 8, "energy": 3}, cooldown=45),
    action("walk", "Take a walk", "movement", "Wander an open lane and clear the mind.", needs={"energy": -3, "safety": 3}, cooldown=20),
    action("visit_market", "Visit the market", "movement", "Browse the market and hear village news.", location="market", needs={"social": 7}, cooldown=60),
    action("visit_tavern", "Visit the tavern", "movement", "Go to the tavern for company.", location="tavern", needs={"social": 10, "energy": 3}, cooldown=60),
    action("seek_shelter", "Seek shelter", "needs", "Take cover at home when afraid or exhausted.", location="home", needs={"safety": 32, "energy": 8}, cooldown=80),
    action("forage", "Forage for food", "livelihood", "Gather a little food from the common land.", location="farm", needs={"energy": -8}, world={"food": 3}, cooldown=75),
    action("work", "Go to work", "livelihood", "Perform the work of your occupation.", location="workplace", needs={"energy": -8, "hunger": -3}, income=6, world={"prosperity": .18}, cooldown=60),
    action("plant", "Plant seedlings", "livelihood", "Invest labor in the next harvest.", location="farm", needs={"energy": -10}, world={"prosperity": .4, "food": 1}, income=3, cooldown=80),
    action("harvest", "Harvest crops", "livelihood", "Bring produce into the shared larder.", location="farm", needs={"energy": -12}, world={"food": 7}, income=4, cooldown=100),
    action("water_garden", "Tend the garden", "livelihood", "Water the communal garden and improve resilience.", location="farm", needs={"energy": -5, "safety": 3}, world={"food": 2, "prosperity": .15}, cooldown=60),
    action("fish", "Fish the river", "livelihood", "Fish from the safe western bank.", location="river_bank", needs={"energy": -6}, world={"food": 4}, income=2, cooldown=90),
    action("bake", "Bake bread", "livelihood", "Turn stored grain into bread for everyone.", location="bakery", needs={"energy": -8}, world={"food": 4}, income=4, cooldown=80),
    action("craft", "Craft useful goods", "livelihood", "Make tools or household goods in the workshop.", location="workshop", needs={"energy": -10}, world={"prosperity": .5}, income=7, cooldown=80),
    action("repair", "Repair public tools", "livelihood", "Repair shared equipment to reduce future hardship.", location="workshop", needs={"energy": -8}, world={"prosperity": .5, "tension": -.25}, income=4, cooldown=90),
    action("trade", "Trade at market", "livelihood", "Sell goods and keep village trade moving.", location="market", needs={"social": 4, "energy": -4}, income=5, world={"treasury": 1, "prosperity": .2}, cooldown=70),
    action("deliver", "Run an errand", "livelihood", "Carry supplies between households.", location="market", needs={"energy": -6, "social": 4}, income=3, cooldown=60),
    action("teach", "Teach a lesson", "community", "Share practical knowledge at the learning room.", location="school", needs={"social": 12, "energy": -5}, world={"prosperity": .25, "tension": -.4}, income=3, cooldown=100),
    action("study", "Study a book", "reflection", "Read at the school and develop a fresh perspective.", location="school", needs={"safety": 4, "energy": -2}, world={"prosperity": .1}, cooldown=70),
    action("research", "Investigate a problem", "reflection", "Check evidence and test a practical idea.", location="school", needs={"energy": -5, "safety": 5}, world={"dread": -.6, "prosperity": .15}, cooldown=100),
    action("heal", "Care for a neighbor", "community", "Offer practical care to someone who needs support.", target=True, needs={"social": 5, "energy": -5}, bond={"affinity": 5, "trust": 6}, target_needs={"energy": 15, "safety": 12}, cooldown=90),
    action("help", "Lend a hand", "community", "Help a neighbor finish a difficult task.", target=True, needs={"energy": -5, "social": 7}, bond={"affinity": 5, "trust": 5}, target_needs={"energy": 8}, cooldown=45),
    action("share_food", "Share a meal", "community", "Offer a meal from the communal larder.", target=True, needs={"social": 10}, target_needs={"hunger": 35, "social": 8}, world={"food": -1}, bond={"affinity": 7, "trust": 5}, cooldown=70),
    action("donate", "Support the commons", "community", "Donate five coins to public services.", location="town_hall", cost=5, world={"treasury": 5, "tension": -.8}, needs={"social": 4}, cooldown=120),
    action("clean_up", "Clean the square", "community", "Improve a shared space through ordinary care.", location="town_hall", needs={"energy": -5, "safety": 3}, world={"prosperity": .2, "tension": -.3}, cooldown=80),
    action("organize_feast", "Organize a feast", "community", "Spend food on a gathering that lifts village spirits.", location="tavern", world={"food": -5, "tension": -2, "dread": -1}, needs={"social": 22, "energy": -8}, cooldown=360),
    action("perform", "Play some music", "community", "Perform in the tavern to ease worries.", location="tavern", needs={"social": 18, "energy": -5}, world={"dread": -.7, "tension": -.5}, income=2, cooldown=90),
    action("dance", "Dance together", "social", "Invite someone to share a carefree dance.", target=True, needs={"social": 18, "energy": -5}, bond={"affinity": 6, "trust": 2}, cooldown=60),
    action("talk", "Start a conversation", "social", "Exchange ordinary news with another villager.", target=True, needs={"social": 20}, bond={"affinity": 4, "trust": 2}, cooldown=25),
    action("greet", "Say hello", "social", "Make a small friendly connection.", target=True, needs={"social": 8}, bond={"affinity": 2}, cooldown=20),
    action("joke", "Tell a joke", "social", "Try to lighten another villager's day.", target=True, needs={"social": 14}, bond={"affinity": 4}, target_needs={"safety": 3}, cooldown=40),
    action("listen", "Listen closely", "social", "Give someone space to be heard.", target=True, needs={"social": 12}, bond={"affinity": 3, "trust": 6}, target_needs={"social": 16, "safety": 5}, cooldown=40),
    action("gossip", "Trade gossip", "social", "Repeat a remembered rumor, making its uncertain origin clear.", target=True, needs={"social": 17}, bond={"affinity": 2, "trust": -1}, world={"tension": .2}, cooldown=55),
    action("share_secret", "Share a confidence", "social", "Entrust a personal worry to a trusted neighbor.", target=True, needs={"social": 18, "safety": 3}, bond={"affinity": 5, "trust": 8}, min_trust=35, cooldown=100),
    action("compliment", "Offer a compliment", "social", "Notice something good about someone.", target=True, needs={"social": 9}, bond={"affinity": 5, "trust": 1}, cooldown=45),
    action("thank", "Express gratitude", "social", "Thank a neighbor for their presence or help.", target=True, needs={"social": 8}, bond={"affinity": 4, "trust": 3}, cooldown=50),
    action("console", "Offer comfort", "social", "Help a worried neighbor feel less alone.", target=True, needs={"social": 9}, bond={"affinity": 5, "trust": 5}, target_needs={"safety": 16, "social": 12}, cooldown=50),
    action("reminisce", "Remember together", "social", "Share an old story and strengthen belonging.", target=True, needs={"social": 15, "safety": 4}, bond={"affinity": 4, "trust": 3}, min_trust=20, cooldown=75),
    action("invite_home", "Invite a neighbor home", "social", "Offer hospitality and a welcome into your life.", target=True, needs={"social": 20}, bond={"affinity": 7, "trust": 5}, min_trust=25, cooldown=100),
    action("give_gift", "Give a small gift", "social", "Spend three coins on a thoughtful gift.", target=True, cost=3, needs={"social": 10}, bond={"affinity": 8, "trust": 2}, cooldown=120),
    action("make_friend", "Deepen a friendship", "social", "Acknowledge a friendship that has grown through trust.", target=True, needs={"social": 20}, bond={"affinity": 6, "trust": 6}, min_affinity=35, min_trust=30, cooldown=120),
    action("debate", "Debate an idea", "conflict", "Challenge another person's view without attacking them.", target=True, needs={"social": 10, "energy": -3}, bond={"trust": 2}, world={"tension": .15}, cooldown=55),
    action("argue", "Have an argument", "conflict", "An escalating disagreement strains a relationship.", target=True, needs={"social": 5, "safety": -4}, bond={"affinity": -8, "trust": -5}, world={"tension": .7}, cooldown=75),
    action("insult", "Say something hurtful", "conflict", "A sharp remark damages trust and may be remembered.", target=True, needs={"social": 3}, bond={"affinity": -12, "trust": -8}, target_needs={"safety": -6}, world={"tension": 1}, cooldown=100),
    action("confront", "Confront a grievance", "conflict", "Bring an unresolved grievance into the open.", target=True, needs={"social": 8}, bond={"affinity": -4, "trust": 1}, world={"tension": .3}, cooldown=90),
    action("fight", "Start a scuffle", "conflict", "A non-graphic adult scuffle leaves both shaken and tired.", target=True, needs={"energy": -20, "safety": -15}, target_needs={"energy": -16, "safety": -16}, bond={"affinity": -20, "trust": -18}, world={"tension": 3}, cooldown=240),
    action("apologize", "Offer an apology", "repair", "Acknowledge harm and begin rebuilding trust.", target=True, needs={"social": 9}, bond={"affinity": 8, "trust": 7}, world={"tension": -.6}, cooldown=80),
    action("forgive", "Offer forgiveness", "repair", "Let a strained relationship take a cautious step forward.", target=True, needs={"safety": 5, "social": 10}, bond={"affinity": 7, "trust": 5}, world={"tension": -.5}, cooldown=90),
    action("mediate", "Mediate a dispute", "repair", "Listen to a tense neighbor and help them find another route.", target=True, needs={"energy": -5, "social": 10}, target_needs={"safety": 10}, bond={"trust": 5}, world={"tension": -1.5}, cooldown=90),
    action("deescalate", "Calm a confrontation", "repair", "Create breathing room for a distressed neighbor.", target=True, needs={"energy": -3}, target_needs={"safety": 14}, bond={"trust": 4}, world={"tension": -1}, cooldown=55),
    action("set_boundary", "Set a boundary", "repair", "Ask for space and restore a sense of agency.", target=True, needs={"safety": 10}, bond={"affinity": -2, "trust": 2}, cooldown=90),
    action("flirt", "Flirt", "romance", "Express interest to a compatible adult who has shown warmth.", target=True, needs={"social": 12}, bond={"affinity": 4, "romance": 8}, cooldown=80),
    action("court", "Spend romantic time", "romance", "Develop a mutual adult romantic connection.", target=True, needs={"social": 20}, bond={"affinity": 6, "trust": 5, "romance": 9}, cooldown=120),
    action("hold_hands", "Hold hands", "romance", "Share a small gesture of mutual affection.", target=True, needs={"social": 13, "safety": 5}, bond={"affinity": 3, "romance": 4}, cooldown=80),
    action("kiss", "Share a kiss", "romance", "Share a consensual kiss with an established romantic connection.", target=True, needs={"social": 16}, bond={"romance": 7, "affinity": 4}, cooldown=100),
    action("form_partnership", "Become partners", "romance", "Agree mutually to a committed adult partnership.", target=True, needs={"social": 22, "safety": 8}, bond={"trust": 10, "romance": 8}, cooldown=1440),
    action("marry", "Marry", "romance", "Celebrate a well-established mutual adult partnership.", target=True, needs={"social": 25, "safety": 10}, bond={"trust": 12, "romance": 6}, world={"tension": -1}, cooldown=10080),
    action("intimacy", "Share private intimacy", "romance", "Consenting adult partners share a private, non-graphic intimate moment.", target=True, needs={"social": 24, "energy": -8, "safety": 5}, bond={"trust": 5, "romance": 6}, cooldown=480),
    action("discuss_family", "Discuss family plans", "romance", "Adult partners discuss whether they both want a child.", target=True, needs={"social": 14}, bond={"trust": 7}, cooldown=720),
    action("try_for_child", "Try for a child", "romance", "Mutually willing adult partners privately try to conceive; outcome is probabilistic and abstract.", target=True, needs={"social": 18, "energy": -8}, bond={"trust": 4}, cooldown=1440),
    action("break_up", "End a partnership", "romance", "End a partnership and remember the separation.", target=True, needs={"social": -18, "safety": -5}, bond={"romance": -60, "affinity": -20}, cooldown=1440),
    action("care_for_child", "Care for a child", "family", "Meet a child's need for food, comfort and attention.", target=True, needs={"energy": -8, "social": 15}, target_needs={"hunger": 25, "safety": 20, "social": 25}, bond={"affinity": 6, "trust": 6}, world={"food": -.5}, cooldown=80),
    action("petition", "Petition the assembly", "civic", "Register a grievance through the village assembly.", location="town_hall", needs={"social": 8, "energy": -3}, world={"tension": -.25}, cooldown=180),
    action("protest", "Join a protest", "civic", "Express public dissatisfaction and press for change.", location="town_hall", needs={"social": 14, "energy": -7}, world={"tension": 1.4}, cooldown=180),
    action("organize", "Organize neighbors", "civic", "Build support for a shared political demand.", target=True, needs={"social": 15, "energy": -5}, bond={"trust": 4}, world={"tension": .5}, cooldown=150),
    action("strike", "Withhold labor", "civic", "Pressure the assembly by refusing a shift.", location="town_hall", needs={"energy": 10, "social": 10}, world={"prosperity": -.7, "tension": 1}, cooldown=360),
    action("revolt", "Lead a revolt", "civic", "A crisis and organized support trigger a non-graphic challenge to village leadership.", location="town_hall", needs={"energy": -20, "safety": -10}, world={"tension": -12, "prosperity": -3}, cooldown=2880),
    action("negotiate", "Negotiate a settlement", "civic", "Seek a practical concession from a neighbor.", target=True, needs={"energy": -5, "social": 10}, bond={"trust": 5}, world={"tension": -1.2}, cooldown=150),
    action("vote", "Attend the assembly", "civic", "Take part in a village decision and reinforce legitimacy.", location="town_hall", needs={"social": 10}, world={"tension": -.7}, cooldown=360),
    action("audit", "Review public accounts", "civic", "Check the accounts and improve public accountability.", location="town_hall", needs={"energy": -5}, world={"treasury": 1, "tension": -.5}, cooldown=180),
    action("guard", "Watch the village", "safety", "Watch the streets and provide visible reassurance.", location="town_hall", needs={"energy": -8, "safety": 8}, world={"dread": -.8}, income=2, cooldown=120),
    action("warn", "Warn a neighbor", "safety", "Share a perceived danger without claiming certainty.", target=True, needs={"social": 7}, bond={"trust": 2}, target_needs={"safety": -3}, world={"dread": .25}, cooldown=90),
    action("prepare", "Prepare emergency supplies", "safety", "Spend effort making the village more resilient.", location="workshop", needs={"energy": -8, "safety": 15}, world={"dread": -.8, "treasury": -1}, cooldown=160),
    action("evacuate", "Help a neighbor to shelter", "safety", "Help a frightened neighbor prepare to leave danger.", target=True, needs={"energy": -8, "safety": 7}, target_needs={"safety": 25}, bond={"trust": 8, "affinity": 5}, cooldown=150),
    action("reassure", "Offer reassurance", "safety", "Ground a neighbor in what the village can do together.", target=True, needs={"social": 9}, target_needs={"safety": 17}, bond={"trust": 4}, world={"dread": -.6}, cooldown=65),
    action("think", "Think it through", "reflection", "Pause to explore a fictional inner thought about current life.", needs={"safety": 4}, cooldown=45),
    action("reflect", "Reflect on a memory", "reflection", "Make meaning from something that happened.", needs={"safety": 5, "energy": 3}, cooldown=80),
    action("plan", "Make a plan", "reflection", "Choose a concrete next step toward a personal goal.", needs={"safety": 7}, cooldown=100),
    action("journal", "Write in a journal", "reflection", "Record a private impression for later reflection.", location="home", needs={"safety": 7, "social": -2}, cooldown=120),
    action("pray", "Find a quiet ritual", "reflection", "Use a personal ritual to feel grounded.", needs={"safety": 9, "energy": 3}, cooldown=100),
    action("grieve", "Make space for grief", "reflection", "Sit with a difficult feeling and begin to recover.", needs={"safety": 5, "energy": 5}, cooldown=120),
    action("explore", "Explore the lanes", "movement", "Look for new details in familiar surroundings.", needs={"energy": -5, "safety": 4}, cooldown=70),
    action("observe", "Watch village life", "reflection", "Notice the people and mood of the village.", needs={"social": 5, "safety": 2}, cooldown=40),
    action("paint", "Sketch the village", "reflection", "Turn a quiet observation into a small piece of art.", needs={"energy": -3, "safety": 6}, cooldown=100),
    action("exercise", "Stretch and exercise", "needs", "Move deliberately to recover confidence and sleep better.", needs={"energy": -8, "safety": 8}, cooldown=180),
]

ACTION_BY_ID = {item["id"]: item for item in ACTIONS}


def action_catalog():
    return deepcopy(ACTIONS)
