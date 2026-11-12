# Hearth action catalog

89 actions. Availability depends on needs, time, resources, relationships, cooldowns and nearby people. The engine rechecks prerequisites before applying a choice.

Generated from `village/data.py`; this is a reference, not a second rules source.

## Needs

| Action | Behavior |
| --- | --- |
| Eat a meal (`eat`) | Take a meal from the shared food supply. |
| Cook supper (`cook`) | Prepare a filling meal at home. |
| Sleep (`sleep`) | Sleep safely at home to restore energy. |
| Take a breather (`rest`) | Rest quietly and recover energy. |
| Wash up (`wash`) | Freshen up at home and feel more settled. |
| Seek shelter (`seek_shelter`) | Take cover at home when afraid or exhausted. |
| Stretch and exercise (`exercise`) | Move deliberately to recover confidence and sleep better. |

## Movement

| Action | Behavior |
| --- | --- |
| Return home (`go_home`) | Walk home and feel grounded. |
| Take a walk (`walk`) | Wander an open lane and clear the mind. |
| Visit the market (`visit_market`) | Browse the market and hear village news. |
| Visit the tavern (`visit_tavern`) | Go to the tavern for company. |
| Explore the lanes (`explore`) | Look for new details in familiar surroundings. |

## Livelihood

| Action | Behavior |
| --- | --- |
| Forage for food (`forage`) | Gather a little food from the common land. |
| Go to work (`work`) | Perform the work of your occupation. |
| Plant seedlings (`plant`) | Invest labor in the next harvest. |
| Harvest crops (`harvest`) | Bring produce into the shared larder. |
| Tend the garden (`water_garden`) | Water the communal garden and improve resilience. |
| Fish the river (`fish`) | Fish from the safe western bank. |
| Bake bread (`bake`) | Turn stored grain into bread for everyone. |
| Craft useful goods (`craft`) | Make tools or household goods in the workshop. |
| Repair public tools (`repair`) | Repair shared equipment to reduce future hardship. |
| Trade at market (`trade`) | Sell goods and keep village trade moving. |
| Run an errand (`deliver`) | Carry supplies between households. |

## Community

| Action | Behavior |
| --- | --- |
| Teach a lesson (`teach`) | Share practical knowledge at the learning room. |
| Care for a neighbor (`heal`) | Offer practical care to someone who needs support. |
| Lend a hand (`help`) | Help a neighbor finish a difficult task. |
| Share a meal (`share_food`) | Offer a meal from the communal larder. |
| Support the commons (`donate`) | Donate five coins to public services. |
| Clean the square (`clean_up`) | Improve a shared space through ordinary care. |
| Organize a feast (`organize_feast`) | Spend food on a gathering that lifts village spirits. |
| Play some music (`perform`) | Perform in the tavern to ease worries. |

## Reflection

| Action | Behavior |
| --- | --- |
| Study a book (`study`) | Read at the school and develop a fresh perspective. |
| Investigate a problem (`research`) | Check evidence and test a practical idea. |
| Think it through (`think`) | Pause to explore a fictional inner thought about current life. |
| Reflect on a memory (`reflect`) | Make meaning from something that happened. |
| Make a plan (`plan`) | Choose a concrete next step toward a personal goal. |
| Write in a journal (`journal`) | Record a private impression for later reflection. |
| Find a quiet ritual (`pray`) | Use a personal ritual to feel grounded. |
| Make space for grief (`grieve`) | Sit with a difficult feeling and begin to recover. |
| Watch village life (`observe`) | Notice the people and mood of the village. |
| Sketch the village (`paint`) | Turn a quiet observation into a small piece of art. |

## Social

| Action | Behavior |
| --- | --- |
| Dance together (`dance`) | Invite someone to share a carefree dance. |
| Start a conversation (`talk`) | Exchange ordinary news with another villager. |
| Say hello (`greet`) | Make a small friendly connection. |
| Tell a joke (`joke`) | Try to lighten another villager's day. |
| Listen closely (`listen`) | Give someone space to be heard. |
| Trade gossip (`gossip`) | Repeat a remembered rumor, making its uncertain origin clear. |
| Share a confidence (`share_secret`) | Entrust a personal worry to a trusted neighbor. |
| Offer a compliment (`compliment`) | Notice something good about someone. |
| Express gratitude (`thank`) | Thank a neighbor for their presence or help. |
| Offer comfort (`console`) | Help a worried neighbor feel less alone. |
| Remember together (`reminisce`) | Share an old story and strengthen belonging. |
| Invite a neighbor home (`invite_home`) | Offer hospitality and a welcome into your life. |
| Give a small gift (`give_gift`) | Spend three coins on a thoughtful gift. |
| Deepen a friendship (`make_friend`) | Acknowledge a friendship that has grown through trust. |

## Conflict

| Action | Behavior |
| --- | --- |
| Debate an idea (`debate`) | Challenge another person's view without attacking them. |
| Have an argument (`argue`) | An escalating disagreement strains a relationship. |
| Say something hurtful (`insult`) | A sharp remark damages trust and may be remembered. |
| Confront a grievance (`confront`) | Bring an unresolved grievance into the open. |
| Start a scuffle (`fight`) | A non-graphic adult scuffle leaves both shaken and tired. |

## Repair

| Action | Behavior |
| --- | --- |
| Offer an apology (`apologize`) | Acknowledge harm and begin rebuilding trust. |
| Offer forgiveness (`forgive`) | Let a strained relationship take a cautious step forward. |
| Mediate a dispute (`mediate`) | Listen to a tense neighbor and help them find another route. |
| Calm a confrontation (`deescalate`) | Create breathing room for a distressed neighbor. |
| Set a boundary (`set_boundary`) | Ask for space and restore a sense of agency. |

## Romance

| Action | Behavior |
| --- | --- |
| Flirt (`flirt`) | Express interest to a compatible adult who has shown warmth. |
| Spend romantic time (`court`) | Develop a mutual adult romantic connection. |
| Hold hands (`hold_hands`) | Share a small gesture of mutual affection. |
| Share a kiss (`kiss`) | Share a consensual kiss with an established romantic connection. |
| Become partners (`form_partnership`) | Agree mutually to a committed adult partnership. |
| Marry (`marry`) | Celebrate a well-established mutual adult partnership. |
| Share private intimacy (`intimacy`) | Consenting adult partners share a private, non-graphic intimate moment. |
| Discuss family plans (`discuss_family`) | Adult partners discuss whether they both want a child. |
| Try for a child (`try_for_child`) | Mutually willing adult partners privately try to conceive; outcome is probabilistic and abstract. |
| End a partnership (`break_up`) | End a partnership and remember the separation. |

## Family

| Action | Behavior |
| --- | --- |
| Care for a child (`care_for_child`) | Meet a child's need for food, comfort and attention. |

## Civic

| Action | Behavior |
| --- | --- |
| Petition the assembly (`petition`) | Register a grievance through the village assembly. |
| Join a protest (`protest`) | Express public dissatisfaction and press for change. |
| Organize neighbors (`organize`) | Build support for a shared political demand. |
| Withhold labor (`strike`) | Pressure the assembly by refusing a shift. |
| Lead a revolt (`revolt`) | A crisis and organized support trigger a non-graphic challenge to village leadership. |
| Negotiate a settlement (`negotiate`) | Seek a practical concession from a neighbor. |
| Attend the assembly (`vote`) | Take part in a village decision and reinforce legitimacy. |
| Review public accounts (`audit`) | Check the accounts and improve public accountability. |

## Safety

| Action | Behavior |
| --- | --- |
| Watch the village (`guard`) | Watch the streets and provide visible reassurance. |
| Warn a neighbor (`warn`) | Share a perceived danger without claiming certainty. |
| Prepare emergency supplies (`prepare`) | Spend effort making the village more resilient. |
| Help a neighbor to shelter (`evacuate`) | Help a frightened neighbor prepare to leave danger. |
| Offer reassurance (`reassure`) | Ground a neighbor in what the village can do together. |
