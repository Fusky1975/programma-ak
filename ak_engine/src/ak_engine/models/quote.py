"""Quote of the Week -- ``HostAK/TP/PROSE/QUOTES.X2`` (header ``"94 2"``:
94 real-world historical quotes, each a 2-line block) plus
``HostAK/TP/SAY.PAS``'s own ``_SQuote`` dispatch (~line 1231):

```
_SQuote: BEGIN
  PR2;
  Say('Quote of the Week:',S_Red);
  PR2;
  qfact:= longint(gdyear)*366 +gdmonth*31-31 +gdday -(7*ord(gameturn=0));
  qfact:= ((qfact-startfact[company]) DIV 7) MOD 94;
  extext:= true; FD('c:\\tp\\prose\\quotes.x2',S_Red,1001+qfact);
  extext:= false;
 END;
```

``FD`` (``RUMORS.PAS``, ~line 2252) is the general ``PROSE/*.X2`` block
reader already confirmed by ``report/prose.py``'s own Phase 58
foundation: it reads the file's own declared ``choices``/``blockdepth``
header (``94 2`` -- 94 blocks of 2 lines each), and since
``1001 <= dex < 2000``, selects block number ``dex-1000`` directly (a
plain 1-indexed lookup, no further randomization -- that branch of
``FD`` is reserved for ``dex >= 2000``/``dex >= 100`` random-choice
cases this dispatch never triggers). ``Pos('quotes',fn) > 0`` is the one
place ``FD`` forces a paragraph break (``PR1``) after *every* line of a
block instead of only between blocks -- so a quote's two lines render as
two separate paragraphs, after the "Quote of the Week:" header's own
paragraph.

**The week-selection formula (`qfact`) is real but not reproducible
here**: `gdyear`/`gdmonth`/`gdday` are the *real* calendar date the host
program was run on, and `startfact[company]` is a per-company offset --
both host-only runtime state with no representation in a parsed
``AK3__T*.K1`` move file and no available source for how either is
initialized (the missing main program's own territory, this project's
recurring, documented gap). This module therefore stops at the same
boundary as ``turn/rename_province.py`` (Phase 150, `Read_T1Names`'s own
real but unavailable `miscfile` input format): the quote table and the
block-lookup mechanism are modeled and real; the caller supplies the
block index (0-93) directly rather than this module guessing at a
calendar-driven rotation it cannot verify.

Quote text and attribution are transcribed verbatim, exactly as they
appear on their own two source lines, including whichever order the
source itself uses (about a third of the 94 blocks state the speaker's
name *before* the quote rather than after it as a trailing attribution
line) -- not reordered or normalized. These are centuries-old,
public-domain historical quotations (attributed to Louis VII, Genghis
Khan, Machiavelli, and similar), the game's own flavor-text data file,
not the user's original content.
"""

from __future__ import annotations


QUOTES: tuple[tuple[str, str], ...] = (
    (
        '"The King of England has men, horses, silk, jewels, fruit, game and everything else.  And we in France have nothing but bread and wine and gaiety!"',
        '-Louis VII, King of France, 1179 A.D.',
    ),
    (
        'St. Louis IX, King of France, speaking to his son in 1244 A.D.:',
        '"I would rather have a Scot come from Scotland to govern France well and justly than that you should govern them ill in the sight of all the world."',
    ),
    (
        'Thomas Jefferson, 1788:',
        '"There is not a single crowned head in Europe whose talents or merits would entitle him to be elected as a town crier in any village in America."',
    ),
    (
        'John II, King of Poland, after routing the Turks from Vienna in 1683 A.D.:',
        '"The immortal God... has blest us with so signal a victory as scarce the memory of man can equal.  Thanks be to Heaven, now the Half-Moon triumphs no longer over the Cross!"',
    ),
    (
        'James I, King of England, 1609 A.D.:',
        '"The state of monarchy is the supremest thing upon earth: for Kings are not only God\'s Lieutenants upon earth, and sit upon God\'s throne, but even by God himself they are called Gods."',
    ),
    (
        'German philosopher George Hegel, 1821:',
        '"In England even the poorest of people believe they have Rights; this is very different from what satisfies the poor in other lands."',
    ),
    (
        'George III, King of England, 1782:',
        '"Knavery seems to be so much the striking feature of Americans that it may not, in the end, be an evil that they will become apart from this Kingdom."',
    ),
    (
        '"It is a political error to practice deceit, if deceit is carried too far."',
        '-Frederick II, King of Prussia, 1740.',
    ),
    (
        'Frederick II, King of Prussia, while rallying his Guards battalion from rout at the battle of Kolin in 1757:',
        '"You Rogues!  Do you want to live forever?"',
    ),
    (
        'Imperial Motto of Frederick III (1415-1493), Holy Roman Emperor and ruler of Austria:',
        '"The whole world is subject to Austria"',
    ),
    (
        'Cardinal Baronio, to Italian scientist and astronomer Galileo Galilei in 1615:',
        '"It is the Holy Spirit\'s intention to teach us how to go to heaven, not how the heavens go."',
    ),
    (
        'Elizabeth I, Queen of England, to her subjects in 1601:',
        '"You have had, and may have, many mightier and wiser princes sitting upon this throne; yet you never had, nor shall have any that will love you better."',
    ),
    (
        'Sir Thomas Elyot, English Diplomat, in 1531:',
        '"Football is nothing but beastly fury and extreme violence, whereof proceedeth hurt; and consequently rancour and malice do remain with them that be wounded."',
    ),
    (
        'Desierius Erasmus, Dutch scholar, 1521:',
        '"Let a King recall that to improve his realm is better than to increase his territory."',
    ),
    (
        'King Charlemagne, after his surprise-coronation as Holy Roman Emperor by the Pope in 800 A.D.:',
        '"I would never have entered the church on that day, though it was an important feast, could I have known the Pope\'s intention in advance."',
    ),
    (
        'German philosopher George Hegel, 1807:',
        '"The Heroes of an epoch must be recognized as its clear-sighted ones; their deeds and their words are the best of their time."',
    ),
    (
        'Henry I, King of England, circa 1100 A.D.:',
        '"An illiterate King is a crowned ass."',
    ),
    (
        'Henry III, King of England, on taking an oath to uphold the Magna Carta:',
        '"These principles I shall keep faithfully and undiminished, as a man, as a Christian, as a soldier, and as a King, crowned and anointed."',
    ),
    (
        '"A prince who desires to maintain his position must learn to be not always good, but to be so or not as needs may require."',
        '-Niccolo Machiavelli, Renaissance political theorist, 1513 A.D.',
    ),
    (
        '"To no one will we sell, to no one will we refuse or delay right or justice."',
        '-The Magna Carta, 1215',
    ),
    (
        'Charles II, King of England, in his proclamation "Articles of War", 1666:',
        '"It is upon the navy under the Providence of God that the safety, honour and welfare of this realm do chiefly attend."',
    ),
    (
        'John Adams, second President of USA, July 4, 1776:',
        '"The Declaration of Independence ought to be commemorated as the day of deliverance... and [celebrated] from one end of this continent to the other, from this time forward, for ever more."',
    ),
    (
        'Attributed to an anonymous Russian diplomat, 1868:',
        '"Every country has its own constitution; ours is absolutism moderated by assassination."',
    ),
    (
        'Pope Leo X, speaking privately of the upcoming election of the Holy Roman Emperor, 1519:',
        '"The Imperial electors will soon go to Frankfurt, and in my opinion the crown will be put up for auction, so that the highest bidder will be elected King of the Romans."',
    ),
    (
        'Leonardo da Vinci, 1483:',
        '"I will make covered cars, safe and unassailable, which will enter among the enemy and their artillery, and there is no company of men at arms so great that they will not break ranks."',
    ),
    (
        'David Leslie, Scottish Parliamentary General, 1643:',
        '"How glorious it would be, in the eyes of God and men, if we managed to hunt the Catholics from England, follow them to France and from there to Rome, to chase the Antichrist and burn the town whence superstition comes."',
    ),
    (
        'Thomas Wentworth, Earl of Strafford, upon his execution as a Royalist in 1641:',
        '"I wish that every man would lay his hand on his heart, and consider seriously whether the beginnings of the people\'s happiness should be written in letters of blood."',
    ),
    (
        'Philip Stubbes, English Puritan, 1583:',
        '"Footeball ... causeth fighting, brawling, contention, quarrel picking, murder, homicide and great effusion of bloode, as daily experience teacheth."',
    ),
    (
        'Sayeth the French monk and diplomat Suger in 1097, after the English King William II failed in his campaign to conquer France:',
        '"Since it is neither right nor natural for Frenchmen to be subject to Englishmen, but rather for Englishmen to be subject to Frenchmen, the outcome of the campaign mocked his vile expectation."',
    ),
    (
        'Lord Acton, British historian, 1887:',
        '"Power tends to corrupt, and absolute power corrupts absolutely.  Great men are almost always bad men, even when they exercise influence and not authority."',
    ),
    (
        'Gebhard Blucher, Prussian Grand Marshal, upon visiting London in 1814:',
        '"What a place to plunder!"',
    ),
    (
        'Nicolas Boileau-Despreaux, Royal French Historian to Louis XIV, after Louis narrowly avoided being hit by a cannonball in 1677:',
        '"Sire, as your Historians Royal, we beg you not to finish our history so soon!"',
    ),
    (
        'Lucien Bonaparte, brother to Napoleon, 1790:',
        '"To tell the truth, Napoleon is a dangerous man in a free country.  He seems to me to have the makings of a tyrant and I believe that were he a King... his name would become an object of detestation to posterity and every right-minded patriot."',
    ),
    (
        'Stephen Decatur, American naval commander, 1815:',
        '"Our country!  In her intercourse with foreign nations, may she always be in the right; but our country, right or wrong."',
    ),
    (
        'Giuseppe Garibaldi, Italion revolutionary general, 1854:',
        '"England is a great and powerful nation, foremost in human progress, enemy to despotism, friend of the oppressed.  If ever England should... require the help of an ally, cursed be the Italian who would not step forward with me in her defence."',
    ),
    (
        'Genghis Khan, 1206:',
        '"It is forbidden ever to make peace with a monarch, a prince or a people who have not submitted to me."',
    ),
    (
        'John Gaule, English Clergyman, speaking on the witch-hunts of 1646:',
        '"Every old woman with a wrinkled face... and a dog or cat by her side, is not only suspected but pronounced for a witch."',
    ),
    (
        "Friedrich von Gentz, Austrian diplomat, at the European council which met to divide Europe after Napoleon's defeat in 1814:",
        '"I sensed as never before the futility of human endeavour, the failings of men who hold the fate of the world in their hands."',
    ),
    (
        'Maximilian I, Holy Roman Emperor, to Henry VIII of England in 1542:',
        '"The King of France is called the most Christian King, but this does him injustice, for he never did a Christian thing.  I am called the most Invincible King, but I have often been overcome... But you are called the richest King, and this is true."',
    ),
    (
        'Viacheslav Plehve, Russian Minister of the Interior in 1903:',
        '"Russia has been made by bayonets, not by diplomacy; and we must decide the questions at issue with China and Japan through bayonets and not through the pens of diplomats... Russia needs a nice little victorious war."',
    ),
    (
        'Giuseppe Garibaldi, Italion revolutionary general, 1849:',
        '"I offer neither pay, nor quarters, nor food; I offer only hunger, thirst, forced marches, battles and death.  Let him who loves his country with his heart, and not merely with his lips, follow me."',
    ),
    (
        "Antoine LaSalle, Napoleon's Hussar (light cavalry) general, 1805:",
        '"Any hussar who isn\'t dead by the age of thirty is a disgrace to the army."',
    ),
    (
        'Sun Tzu, General of ancient China, circa 500 b.c.:',
        '"There has never been a protracted war which benefited a country."',
    ),
    (
        'Walter Bagehot, British political writer:',
        '"The reason why Monarchy is a strong government is, that it is an intelligible government.  The mass of mankind understand it, and they hardy anywhere in the world understand any other."',
    ),
    (
        'Boris Godunov, Tsar of Russia, 1598:',
        '"May God be my witness that there will never be a poor man in my Tsardom!  And even to my last shirt I will share with all."',
    ),
    (
        'Lazare Carnot, Superintendent of Generals in Revolutionary France, 1794:',
        '"The General Order is always to manoeuvre in a body and on the attack; ...to use the bayonet on every possible occasion; and to follow up the enemy remorselessly until he is utterly destroyed."',
    ),
    (
        'William Cobbett, English radical:',
        '"Machines are the produce of the mind of man; and their existence distinguishes the civilized man from the savage."',
    ),
    (
        'Pope Gregory VII, 1081:',
        '"Who does not know that kings and rulers presumed because of blind greed and intolerable arrogance to make themselves masters of other men, their equals, by means of pride, violence, bad faith, murder and almost every other kind of crime?"',
    ),
    (
        'Henry IV, King of France, 1577:',
        '"Those who follow their conscience are of my religion; and, for my part, I am of the same religion as all those who are brave and true."',
    ),
    (
        'Paul Hentzner, German tutor, 1598:',
        '"The English are powerful in the field, successful against their enemies, impatient of anything like slavery, vastly fond of great noises that fill the ear, such as the firing of cannons, drums, and ringing of bells."',
    ),
    (
        'Horatio Nelson, English Admiral, to a midshipman under his command in 1793:',
        '"Firstly you must always obey orders, without attempting to form any opinion of your own... Secondly, you must consider every man your enemy who speaks ill of your king; and thirdly, you must hate a Frenchman as you hate the Devil."',
    ),
    (
        'Antoine de Saint Just, French revolutionary, 1792:',
        '"What common foundation of justice is there between humanity and kings?... It is impossible to reign innocently... Every citizen posseses the same right over a king that Brutus had over Caesar."',
    ),
    (
        'Saladin, Moslem Sultan and General, 1188:',
        '"When God has given into my hands the rest of the Holy Land, I shall divide my State among my children.  I shall embark on that sea to subdue the isles and countries of the West.  I will not rest until there is no longer a single infidel on earth."',
    ),
    (
        'Tamburlaine, Tartar Emperor, circa 1380:',
        '"The whole area of the inhabitable world is not worth having more than one monarch."',
    ),
    (
        'Heinrich von Treitschke, German historian and politician, 1875-95:',
        '"The English all think Soap is Civilization."',
    ),
    (
        'John Zizka, Czech rebel, 1421:',
        '"Defend youselves bravely against the misdeeds which those Germans commit against you, follow the example of the Czechs of old who, their pikes firmly propped, defended not only God\'s cause but their own also."',
    ),
    (
        'Oliver Goldsmith, English writer, 1760:',
        '"A Russian fort in the western parts of Europe... would be like the possession of a floodgate; and whenever ambition, interest or necessity prompted, they might then be able to deluge the whole western world with a barbarous inundation."',
    ),
    (
        'Pope Gregory VII, speaking of his election to the Papacy in 1073:',
        '"...there arose a great confusion and shouting of the people; and they rushed upon me like madmen, leaving me no opportunity or time to speak or seek advice.  They dragged me with violent hands to this Papal rule, for which I am so unfitted."',
    ),
    (
        'The Times, English newspaper, reporting on French plans to build 34 new ships in 1798:',
        '"Good news this for old England!  It saves us the trouble and expense of building them ourselves, for they are sure to find their way into our ports."',
    ),
    (
        "Ralph, Abott of Coggeshall and monastic chronicler, reporting on King John's journey through the fens [swamps] in 1216:",
        '"A very great grief troubled John, for he had lost some of his packhorses with different kinds of household effects...  Many of his household, also, were drowned in the waters of the sea and sucked into the quicksand there."',
    ),
    (
        'Ernest Renan, french historian, 1871:',
        '"War is, in a sense, the whip preventing a country from going to sleep and forcing satisfied mediocrity to shake off its apathy."',
    ),
    (
        'Cardinal Jean Paul de Gondi, French political intriguer, 1644:',
        '"I resolved that I would fulfill scrupulously every duty of my profession and that I would be as zealous for the welfare of others as I would be wicked for myself."',
    ),
    (
        'King Henry V, at the battle of Agincourt in 1415, when asked if he did not wish for more troops (he was outnumbered 20,000 to 5,000):',
        '"Do you not believe that the Almighty, with this small force of men on his side, can conquer the hostile arrogance of the French, who pride themselves on their numbers and their own strength?"',
    ),
    (
        'King Henry V, at the siege of Rouen in 1418:',
        '"I act in everything with kindness and mercy, for I am forcing Rouen into submission by starvation, not by fire, sword or bloodshed."',
    ),
    (
        'King Henry VIII, 1545:',
        '"I see and hear daily that you of the Clergy preach one against another, inveigh one against another without charity or discretion... Thus all men, almost, be in variety and discord..."',
    ),
    (
        'Winston Churchill, in the dedication to his book "The Second World War", 1948:',
        '"In War: Resolution;   In Defeat: Defiance;   In Victory: Magnanimity;   In Peace: Goodwill."',
    ),
    (
        'George Villiers, Earl of Clarendon and British diplomat, 1846:',
        '"Spanish dynasties come and go; Spanish Kings come and go; and Spanish ministers come and go; but there is one thing in Spain that is always the same:  they never answer letters."',
    ),
    (
        'Louis XIV, King of France, 1669:',
        '"Every time I fill an empty ministerial office, I make a hundred men discontented and one ungrateful."',
    ),
    (
        'Louis XIV, King of France, speaking to his son while on his deathbed, 1715:',
        '"You will soon be king of a great kingdom... Try to keep peace with your neighbours.  I have loved war too much; do not copy me in that nor in my extravagance... Relieve your people as soon as you can, and do what I have been too unlucky to do."',
    ),
    (
        'John of Winterthur, German chronicler, 1315:',
        '"In 1315, a certain rustic people, who live in the valleys called \'Swiz\', trusted in the strong bulwark of their mountains; they gave up the obedience, payments and services which they owed the Emperor, and prepared to resist him."',
    ),
    (
        'Samuel Johnson, English writer, 1775:',
        '"George the First knew nothing, and desired to know nothing; did nothing, and desired to do nothing; and the only good thing that is told of him is, that he wished to restore the crown to its hereditary successor."',
    ),
    (
        'George Winstanley, English radical, 1649:',
        '"None ought to be lords or landlords over another, but the earth is free for every son and daughter of mankind to live free upon."',
    ),
    (
        'Thomas Wolsey, Lord Chancellor of England, commenting on Henry VIII in 1530:',
        '"...rather than he will miss or want part of his appetite, he will hazard the loss of one-half of his kingdom."',
    ),
    (
        'Francesco Capello, Venetian Ambassador to England, 1502:',
        '"The English do not believe that there are any other people than themselves, or any other world than England:  and whenever they see some handsome foreigner, they say \'he looks like an Englishmnan\' and \'What a pity he is not English.\'"',
    ),
    (
        'Hugh Peters, independent English preacher, upon his return from the American colonies in 1646:',
        '"I have lived in a country where in seven years I never saw a beggar, nor heard an oath, nor looked upon a drunkard: why should there be beggars in England when there is so much work to do?"',
    ),
    (
        "Francesco Petrarch, Italian poet, describing the effects of Edward III's French campaign in 1361:",
        '"Paris itself, the capital, was surrounded, up to its gates, with a burned and wasted land.  It seemed to tremble with horror at its adversity, and even the Seine that penetrates its walls seemed to mourn in terror at the city\'s fate."',
    ),
    (
        'Philip II, King of France, explaining his refusal to join a Crusade in 1209:',
        '"I have two huge lions tearing at my flanks,the so-called Emperor Otto and John, King of England.  Both try with all their might to upset the Kingdom of France.  I cannot leave the country myself or even do without my son here."',
    ),
    (
        'Novgorod Chronicle (an official Russian history), telling of the victory of Alexander Nevsky at Pskov in 1242:',
        '"And there was a great battle with the Germans and Estonians, with the clash of shattering spears and the crash of swords so that the frozen sea began to move; and the ice could not be seen, for everywhere was covered in blood."',
    ),
    (
        'Alfred the Great, King of West Saxony, 897:',
        '"A king\'s raw materials and instruments of rule are a well-peopled land, and he must have men of prayer, men of war, and men of work."',
    ),
    (
        'Lord Burghley, English statesman and Treasurer to Elizabeth 1, on the English expedition against Ireland, 1597:',
        '"I see no good end there, only a perpetual charge here to the realm in levying still more men... I lament it, to see the great waste of people of the English, and of armour and munition."',
    ),
    (
        'Thomas Coventry, English politician and naval advocate, 1635:',
        '"Our wooden walls are the strength and safety of our kingdom, and bring our Riches and Wealth."',
    ),
    (
        'Francois de la Mothe-Fenelon, Archbishop of Cambrai, in a letter to Louis XIV in 1694:',
        '"Your peoples die of hunger...  France is a vast hospital...  There is only bitterness and despair... You relate everything to yourself as though you were God on earth."',
    ),
    (
        'Francis I, King of France, after losing the Battle of Pavia in 1525:',
        '"All is lost, except for my honor and my life."',
    ),
    (
        'Frederick Barbarossa, Holy Roman Emperor, speaking to the pope after an anti-Papal revolution in 1155:',
        '"Do you know where the ancient glory of Rome and its stainless and invincible courage have gone?  All these things are with us Germans.  With us are your consuls, your senate, your soldiery."',
    ),
    (
        'Sir Christopher Hatton, Lord Chancellor of England, 1589 (in asking for more naval funds, after England had defeated the Spanish Armada):',
        '"England hath been accounted hitherto the most renowned kingdom for valour and manhood in all Christendom, and shall we now lose our old reputation?  If we should, it would have been better for England to have never been born."',
    ),
    (
        'Pope Julius II, in reply to Michelangelo, who had asked which of his artistic tools the Pope would like to try (1506):',
        '"Nay, give me a sword, for I am no scholar."',
    ),
    (
        'Saint Ignatius Loyola, Spanish soldier and founder of the Jesuit Order, 1522:',
        '"To arrive at the truth in all things, we ought always to be ready to believe that what seems to us white, is black if the hierarchical Church so defines it."',
    ),
    (
        'Raymond Lull, Spanish mystic and missionary, while debating with a Moslem (Hama the Saracen) in 1308:',
        '"The Christians build hospitals in which they receive the poor, the sick, and travellers, and in each city they have one, two or even three hospitals.  But I never heard that the Saracens have more than two hospitals, at Tunis and Alexandria."',
    ),
    (
        'Martin Luther, German theologian and reformer, 1525:',
        '"In my opinion it is better that all of the peasants should be killed rather than that the sovereigns and magistrates should be destroyed, because the peasants take up the sword without God\'s authorization."',
    ),
    (
        'Napoleon Bonaparte, French Emperor, 1804:',
        '"Power is my mistress.  I have worked too hard in conquering her to allow anyone to take her from me or even to covet her."',
    ),
    (
        'Philotheus, Russian monk and scholar, in a letter to Czar Basil III in 1510:',
        '"The church of old Rome fell because of its heresy; the Second Rome, Constantinople, was sacked by infidels; but now the church of your mighty realm, the Third Rome, shines brighter than the sun, and a Fourth Rome there shall not be."',
    ),
    (
        "Peter Wentworth, champion of Parliamentary rights in Queen Elizabeth I's reign, 1576:",
        '"In this House, which is termed a place of free speech, there is nothing so necessary for the preservation of the prince and State as free speech; and without this it is a scorn and mocker to call it a Parliament House."',
    ),
    (
        'John Wilkes, English radical politician, attacking the speech of King Charles in 1763:',
        '"In vain will such a man, or the foul dregs of his power, the tools of despotism and corruption, preach up \'the spirit of concord\'.  They have sent the spirit of discord through the land."',
    ),
    (
        'William I, first Norman King of England, 1066:',
        '"It is in the defence of right that I have crossed the sea into this country. I do not think it right that my men or Harold\'s men should perish in a quarrel that is none of their making. I am therefore ready to risk my life in a duel to the death."',
    ),
)

def quote_of_the_week(index: int) -> tuple[str, str]:
    """Look up block ``index`` (0-93) of :data:`QUOTES`, matching
    ``_SQuote``'s own ``dex-1000`` 1-indexed lookup shifted to 0-indexed
    (``index=0`` is the block a real ``qfact`` of ``0`` would select).
    Raises ``IndexError`` for an out-of-range index rather than silently
    wrapping -- unlike the real ``MOD 94`` in ``_SQuote``'s own `qfact`
    computation, this project never computes `qfact` itself (see the
    module docstring), so there is no wraparound behavior to replicate.
    """

    return QUOTES[index]
