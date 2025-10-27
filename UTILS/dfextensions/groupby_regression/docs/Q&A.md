


## Motivation - Iteration 1 (2025-10-27 07:00)

Before answering the questions, I would like to describe in more detail what is being done and why.

* 0.) We are trying not only to describe a multidimensional function but also to estimate statistical 
   properties of the probability density function (PDF) itself (e.g. using quantiles).
* 1.) LHC/my specific: We are working with both unbinned and binned data, as well as machine learning 
   algorithms, depending on data availability. In the case of ALICE, we usually have a huge amount of data. 
 For example, for tracks we have 500 kHz × 10 → 5 × 10^6 tracks per second, measuring for O(10–15 hours) per 
 day. This data is either histogrammed in multidimensional histograms or, by default, we sample it using 
  "balanced semi-statfied" sampling, populating the variables of interest homogeneously (e.g. flat pt, flat PID).
   This is very important as PDF of Pt and PID is highly unbalanced (exponential, power-law, etc).
   With this approach, we reduce the input data volume by an order of magnitude and enable iterative refinement  
  of the PDF estimation.
* 2.) Extracting PDF properties in multidimensional space has the advantage of enabling post-fitting of 
  analytical models for normalised data. Quite often, we do not have analytical models for the full distortion 
  in (3D+time), but we can have an analytical model for the delta distortion time evolution. 
  In my current studies, for example, we are fitting a two- exponential phi-symmetric model of distortion 
  due to common electric field modification.


### Q1: Does this capture your motivation accurately?

- There are several factors we must consider, as described above.
- Quite often (but not always), we have a large amount of data. Frequently, we are limited by memory and 
  CPU for processing (see above). Normally, I try to parallelise if the data sets are independent, 
  but using more than 4 GB of data in memory is problematic. Using pre-sampling for unbinned data scenarios 
 helps, as the original data are statistically highly unbalanced (Exponential(mass) - PID, Power-law(pt), etc.).
- In many cases, the problem is not only the sparsity of the data. Our data are "random". 
 To obtain a reasonable estimate of the characterisation of the corresponding PDF, we need substantial 
 statistics for each bin. That is our major obstacle, which we are trying to address.

### Q2: GPT question Should I emphasize more??
  
    The statistics/sparsity problem (mathematical angle)
    The physics context (ALICE TPC, particle physics)
    The software engineering angle (reusability, API design)
    Balance is good as-is
* After my comments above, I think the motivation section will be rewritten. We have to emphasise 
  statistical and mathematical considerations as I described above – estimation of the PDF and later 
  functional decomposition using partial models and some kind of factorisation.
* We should show examples from ALICE.
* The software has to be reusable, as the problem is generic, and we need a generic solution.


### Q3: The tone is currently technical but general. Should it be: (Qestion for Gemini and GPT)

    More mathematical (equations, formal notation)
    More practical (concrete examples upfront)
    Current level is appropriate

I am not sure; I will ask GPT and Gemini about this. Some mathematics would be good, but I have a markdown file with limited mathematical capabilities.
I think we should balance mathematics and practical examples.


### Q4: Any missing key points or mis-characterizations?

* We should place greater emphasis on the statistical estimation problem; refer to my introduction.

* The motivation should be grounded in these defined problems, with the ALICE examples serving to support this.

* For software aspects, we should highlight reusability and API design, as the problem is generic and requires a 
  generic solution.

* I presented the problem previously in several forums – internal meetings, discussions with the ROOT team, and ML 
  conferences several times – but it was difficult to explain. People did not understand the statistical estimation 
  problem, possible factorisation, and later usage in analytical (physical model fitting) using some data 
  renormalisation as I described above.

* We do not have models for everything, but quite often we have models for normalised dlas-ratios in multidimensional space.


Q5: Should I add a diagram/figure placeholder (e.g., "Figure 1: Sparse 3D bins with ±1 neighborhood")?
- Yes, a diagram would be helpful. 
- A figure illustrating sparse 3D bins with ±1 neighborhood would effectively convey the concept 
 of sparsity and the challenges associated with estimating PDF properties in such scenarios. But I am not sure how to do it. 


## Motivation - Iteration 1 (2025-10-27 09:00)

Before answering the questions, I would like to add some use cases:
* Distortion maps already in use
* Performance parameterisation (e.g. track pT resolution as a function of pT, eta, occupancy, time)
    * track matching resolution and biases
    * V0 resolution and biases
    * PID resolution and biases
    * Efficiency maps
    * QA variables (chi2, number of clusters, etc.)
    * Usage in MCto Data remapping
  
* Keep in mind that RootInteractive is only a small subproject for interactive visualisation of the data.  

### Q1: Does Section 1 now accurately capture:
* The PDF estimation focus?
* Balanced sampling strategy?
* Factorization approach?
* Connection to RootInteractive?

===> 

* I think it is more or less OK.
* A balanced sampling strategy is mentioned, but we need more details. In some use cases, we sample down by a factor 
of \(10^3\)–\(10^4\) to obtain a manageable data size, making further processing feasible.
* RootInteractive is just one subproject for interactive visualisation of extracted data.
*Comment on the current version example: In a particular case, I use 90 samples for distortion maps – in reality, 
we use 5–10 minute maps, but in some cases, we have to go to O(s) to follow fluctuations. Obviously, we cannot do 
this with full spatial granularity, so some factorisation will be used.

### Q2: Tone and depth:

* Is the mathematical level appropriate?
  * I will ask GPT/Gemini for feedback on this.
* Should I add equations (e.g., kernel weighting formula)?
    * Yes, adding equations would enhance clarity. However, we should ask PT and Gemini.
* Is the ALICE example clear and compelling?
    * We need distortion map examples and performance parameterisation examples to make it clearer.

### Q3: Missing elements:

* Any key concepts I still missed?
* Should I reference specific equations from your paper?
* Need more or less technical detail?



I included something at the beginning (performance parametrisation case), but I am not sure how much we 
can emphasise it without losing the audience. However, it can be mentioned in the motivation section – 
categories – and later in the example sections.

### Q4: Structure:

Are the subsections (1.1-1.5) logical?
Should I reorganize anything?
* I think the structure is OK for now. We can also ask GPT/Gemini for feedback on this.

### Q5: Next steps:

* Should we send Section 1 to GPT/Gemini now?
* Or continue to Section 2 first?

We need GPT/Gemini review before proceeding to Section 2.