# PRD & Problem Context
Review the design specs below by Forethought. 

# Ambient superforecasting
The most direct form of strategic awareness is simply knowing what's likely to happen. Today, when people want to understand how situations might develop, they mostly rely on intuition, pundit commentary, or — if they're unusually diligent — tracking down relevant prediction markets or expert forecasts. But this is slow and effortful, and even experts are often poorly-calibrated. Future AI driven technologies could make general forecasting as much of a science as weather forecasting is today,3 and calibrated probabilistic predictions as accessible as a search query.
Design sketch: An automated (and integrated) forecasting system that takes in natural-language questions, operationalizes them, then estimates likelihoods, and finally distills and communicates the answers to the user.
Hand-drawn design sketch showing an AI forecasting interface where a user asks “How good will UK AI be in 2 years?” and the system operationalizes the question, generates forecasts, and returns summarized results with charts and re-operationalized queries.
Image
How this could work under the hood:
The tool explores possible operationalizations of the question4 and selects a few (perhaps with user feedback)
For each operationalized question, it runs a specialized system (fine-tuned for forecasting performance), which pulls some reference classes then searches for other relevant info (maybe including private data from the user) to produce calibrated probabilities/distributions
The results are then distilled and translated into a format that works well for the specific user (including an explanation of how the answers might diverge from what the user is imagining/trying to predict)
The tool might also caution users when questions concern areas in which its track record is weaker, suggest related questions or precursors/trends to pay attention to, pull out different scenarios, explore what the key disagreements driving variation in forecasts are, etc.
Feasibility
A basic version of this is already approachable. LLMs can generate operationalizations of natural-language questions, pull relevant base rates and information, and produce probability estimates. Current systems are comparable to strong human performers.5 Compared to a baseline of intuition and pundit commentary, even a system that's mediocre by superforecaster standards could be useful if it was smoothly integrated into people’s workflows (handling operationalization in the background and providing useful summaries and explanations in a timely fashion).
The challenges for a truly great version center on quality of predictions, calibration, and quality of explanations. Sufficiently good systems might be better than any unaided human, so that it becomes almost mandatory to consult them. And while current LLMs have inconsistent calibration, and often don't know when they're out of distribution, this is a key problem because some of the questions that matter most are among those where base rates help least and novel reasoning matters most.
There may be good pathways to improvement. Forecasting is a domain with clear feedback signals: questions resolve, and you can score predictions. This enables fine-tuning on track record, and potentially self-play setups where systems generate questions, make predictions, and learn from outcomes. LLMs trained on historical data with strict cut-off dates could provide a testing ground for experiments about the best methods. A system that routes questions to specialized sub-models based on domain, and that learns over time which question-types it handles well, could improve substantially through iteration.
Possible starting points // concrete projects
How could we work towards this target? Here are some ideas:
Build a baby version of the tool. This could help us notice obstacles or opportunities that would have been hard to predict in advance. You might focus on the tech side here (e.g. seeing how much value you can get out of current (fine-tuned) LLM agents with some scaffolding) or on the UI side (e.g. assuming that the tech will improve and focusing on making an interface that people love).
Build subcomponents. Ideas:
Focus on operationalization and question generation. For example, you could build a tool that explores all the ways in which operationalizations might fail to capture what was really intended with the forecast
Build tools that help forecasters and forecasting systems to find and collect reference classes
Develop automated “forecaster” tools that put numbers or distributions on operationalized questions
Build a system which explains forecasts to users
Build ways to develop and test this kind of tech. Ideas:
Set up a platform that automatically generates as many operationalized forecasting questions as possible (on some specified time scales) to run ongoing tests comparing different automated forecasting systems6 
Alternatively, try to make good simulated environments for this, and explore how well forecasting performance in simulated environments translates to real-world forecasting performance
Explore “fuzzy prediction grading” setups
Curate high-quality datasets of natural-language questions paired with sets of operationalized questions that help to answer them
Try to get a self-play set-up to work, where systems generate questions, make predictions, then learn from outcomes
Collect historical data with strict cut-off dates to use as a testing ground for the best forecasting methods (there are existing attempts to do this even for long-ago cutoff dates, although implementation details can pose problems)
Integrate forecasting features into existing infrastructure. Work with tech infrastructure providers to try integrating some forecasting-like features into their platforms.

## Other Links from their Page
https://www.broadstreet.blog/p/history-llms-giving-the-past-a-voice
https://arxiv.org/abs/2506.00723
https://www.sciencedirect.com/science/article/pii/S0169207024000700
https://proceedings.neurips.cc/paper_files/paper/2024/hash/5a5acfd0876c940d81619c1dc60e7748-Abstract-Conference.html
https://www.science.org/doi/full/10.1126/sciadv.adp1528
https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5066286
https://arxiv.org/abs/2206.15474
https://arxiv.org/abs/2310.13014


# Scenario planning on tap
Point predictions are useful, but many decisions require exploring possibility space more broadly. What happens if we take action A versus action B? What are the key uncertainties, and how do outcomes vary depending on how they resolve? Scenario planning addresses this — but today it's expensive and slow, typically requiring facilitated workshops and significant expert time. The right AI scaffolding could automate much of this process, letting users quickly generate and explore coherent narratives about possible futures.
Where ambient superforecasting answers "what will probably happen?", scenario planning answers "what might happen, and what would drive different outcomes?".
Design sketch
A platform for fully automated scenario planning. The user enters a textual description of a scenario and proposed intervention. The system helps them to make key decisions about scenario set-up, then runs hundreds of natural-language simulations to explore how the situation could evolve, and reports back key statistics, hinge points, and takeaways, with a queryable interface.
Hand-drawn sketch of an AI scenario planning interface showing a user query about California seceding, a scenario map with branching outcomes, leverage points, simulations, and probability-weighted results.
Image
Under the hood, it does something like:
Fleshes out the scenario, with possible choices about setup detail
Letting the user choose option A vs B vs C, treat this as a variable to explore, or write their own detail
Analyses the scenario to pick out key actors and forces (spinning up background research processes if appropriate to better inform the model)
Steps forwards in time, using natural language simulation to get decisions from actors (as though they are human players in a roleplaying game), and a “game-master” system making judgement calls about the relative impact of different decisions and background forces
Runs this scenario many times over
Boots up an automated research project, analysing key patterns in the data represented by the various scenario runs
Returns a queryable interface summarizing likelihoods of different key outcomes, highlighting important causal dynamics, and allowing “what if” exploration of alternative interventions
Desirable extra features:
Toolset to integrate relevant historical data and existing thinking and context as input data for the scenario
Integrated mathematical models for more accurate simulation of parts of the scenario
Search for leverage, flagging:
low-probability high-impact scenarios
parts of the scenario where small changes could swing the outcome
Feasibility
Again, a basic version is eminently achievable: LLMs can generate plausible narratives, simulate agent decisions, and run many scenarios cheaply. Even without strong validation, a tool that helps users explore a wider space of possibilities than they'd consider otherwise could have value — scenario planning has always been about stretching thinking rather than robust prediction.
The challenges for a truly great version center on validation and trust. If the system generates scenarios about 2030, we can't check whether they're informative until 2030. We can use proxies — backtesting on historical scenarios, consistency checks, comparison with expert judgment — but none fully resolve whether outputs capture real dynamics versus just being coherent stories. The "game master" making judgment calls about how situations evolve is doing a lot of work, and systematic biases there would contaminate everything downstream.
Pathways to improvement are less clear than for forecasting, because feedback is slower and noisier. But some approaches might help: running scenarios on historical situations where we know how things played out; comparing scenario outputs against prediction markets or expert forecasts on near-term questions; building in explicit uncertainty about which dynamics are driving outcomes. Over time, the track record of the parts of scenarios that do resolve could inform trust in the parts that don't.
There are potentially strong synergies between forecasting and scenario planning. As forecasting gets better, those expert judgements could mean better, more grounded judgement calls from the “game master” system in scenario planning. And one tool that advanced forecasting systems may want to use (after experimental validation) is scenario planning to think through novel situations.
Possible starting points // concrete projects
Learn from people doing scenario planning. Work with people already doing scenario planning work to see which pieces can most productively be automated and how.
Build an LLM-powered wargame simulator. Develop a system that can run through many instances of a game whose rules have already been established.
Use LLMs with a historical cutoff to test methodologies. Work with LLMs with a historical knowledge cutoff to do science on which scenario planning methodologies are most informative about future developments.

# Automated OSINT
The previous technologies focus on understanding the future. But strategic awareness also requires understanding the present — getting an accurate picture of the world, knowing what to pay attention to, and understanding what actors are doing and why. OSINT analysts and investigative journalists do this kind of analysis, but it's time-consuming and therefore expensive. This both means that most public coverage is underinformed, and that large organisations and state intelligence agencies often have an information advantage over the rest of society. Proper automation has the potential to make this kind of analysis cheap and routine, making it much easier for broader society to understand what’s happening.
Where forecasting and scenario planning help with "what will happen?", automated OSINT helps with "what's really going on?".
Design sketch
An AI-driven OSINT system (that can also make use of private data) lets users “double-click” on any reported action or statement, and get a report showing key hidden variables, likely incentives, and inferences that can be drawn.
Hand-drawn sketch illustrating an automated OSINT system that pulls information from news sources, filters and analyzes it, pools it with other data, and presents summarized insights to users through a dashboard interface.
Image
Under the hood, this might look something like:
A database — hard info + cached inferences/hypotheses about orgs/people
An analysis engine — takes a news story, maps out how it relates to the info in the database, and makes fresh inferences
A summarizer, distilling just the most important points to report back to users, in a queryable interface
Integration with other tools to make asking the tool and granting relevant data access trivial
Start with a single domain (e.g. geopolitics; frontier tech), recruit experts to advise on best practice, and build a system that for any news story returns a page or so of bullets showing plausible incentives, noticeable updates on hidden variables, and other key facts.
Feasibility
Much relevant information is public — financial disclosures, organizational structures, stated positions, historical behavior. LLMs are reasonably good at synthesizing this material and generating hypotheses about incentives. Even a system that just surfaces "here are three possible explanations for this action, with evidence for each" could beat the baseline of news coverage that skips incentive analysis entirely. 
However, there are still some major challenges.
Private information. Much relevant information is also private. Actors with privileged access to that information will have a big advantage. And there are factors which could compound this problem:
The situations where this analysis would be most valuable are often where information is most hidden. 
Automated OSINT itself will create further incentives to selectively reveal information.
Our best guess is that there’s so much room for improvement based on public information, that automated OSINT would still be net positive — but we’re not confident, and this would be good to stress-test.
Accuracy and confidence calibration. Generating plausible theories is easy; knowing which is correct is hard, sometimes impossible from public information alone. And there's a risk of false confidence — presenting hypotheses as more certain than they are. If these analyses are broadly relied upon, this could cause harm. Pathways to improvement might include: 
Building a track record in domains where incentives are relatively legible and outcomes eventually become clear (corporate behavior around earnings, documented geopolitical dynamics).
Learning which types of situations the system analyzes well versus poorly.
Integrating with forecasting tools so that hypotheses generate testable predictions. 
The goal would be a system that gets better at knowing what it knows — distinguishing cases where it can say something meaningful from cases where it's just pattern-matching.
Possible starting points // concrete projects
Learn from OSINT specialists. Work with OSINT analysts and investigative journalists to identify the parts of their workflows that would most benefit from automation, and how best to do that.
Build a browser extension. Develop a browser extension that allows users to click on highlighted claims and see a synthesis of existing OSINT information on the claim.
Create a newsletter for the educated public. Initially this could just be a system which takes existing OSINT analysis and summarises it. Eventually the system could do this analysis itself. Transparent methodology could help the newsletter to be more trusted than traditional media, which is often politically slanted in its analysis.
Auto-Bayesian controversy resolver. When two parties make conflicting claims, calculate the relative probabilities (for example, "Company says hack was nation-state (23% likely), while competitors say it was an insider threat (77% likely)"). Show which evidence supports which hypothesis, and let the reader put in their own priors to infer conclusions.


# Cross-cutting thoughts
Adoption pathways
This cluster of technologies share some characteristics:
They’re potentially powerful forms of what is essentially knowledge-creation
They may require significant time investment from the user’s perspective to get the most out of them, and may require large inference budgets
This means that rather than being mostly a consumer-facing technology, the primary users are more likely to be governments, companies, and other organizations. Consumers may eventually use some version of these technologies (especially after they get both good and cheap), but in the interim the main way that they are likely to benefit the broader public passes through other organisations — as is true for many existing mechanisms of knowledge production. For instance, forecasting features might begin to be embedded in search; or OSINT analysis could form the basis of news articles, or a new verifiably neutral site able to provide fair analysis of politically sensitive situations.
Getting tools adopted by these intermediary organisations is a different kind of challenge to getting broad adoption. The tools don’t just need to be good for the organisation overall - adopting them also needs to be in the interests of some particular person or group within the organisation, who’ll need to put their reputation and organisational resources on the line to get it to happen. Smart adoption strategies for tools for strategic awareness are likely to be sensitive to these dynamics — working out who might be the internal champions for the new technology, and what they’d need to want it.
Ultimately a central challenge will be trust. How much do people believe the analysis that is coming out of these tools? Ideally this trust will be grounded in track record (so one key thing to aim for is making the tech good and then demonstrating that); although of course many other factors feed into trust.
Other challenges
As well as adoption challenges, there are a few other issues for tools for strategic awareness:
Timing. Some of these technologies may need to be quite good before there's strong demand. 
This suggests that for some applications, the right approach might be building foundational components and track record now, while waiting for capabilities to improve. 
Harms from overconfidence. If adoption goes too well — if people trust the outputs of these tools too much — this could lead to badly calibrated decisions.
This makes it particularly important to track and publish where these systems perform well versus poorly.
Misuse. As we mentioned above, all of these tools could be used to further bad ends. 
Two classes of bad effects we might worry about are:
Maybe these tools could make it easier for people to scheme, hatching plans that would help them personally at the expense of the broader world (potentially in illegal ways).
If the tools really reward ever-larger investment of inference compute to get better and better performance, this could provide a mechanism whereby the rich get richer — those actors who can afford the strongest foresight using it to outmanoeuvre or manipulate others.
It could be important to better anticipate and work to head off these failure modes!