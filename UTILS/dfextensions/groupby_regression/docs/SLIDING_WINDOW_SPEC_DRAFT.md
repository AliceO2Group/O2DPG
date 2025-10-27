# Sliding Window GroupBy Regression - Specification Document

**Authors:** Marian Ivanov (GSI/ALICE), Claude (Anthropic)  
**Reviewers:** GPT-4, Gemini  
**Date:** 2025-10-27  
**Version:** 0.1 (Draft)

**Note:** ALICE-specific acronyms and terminology are explained in Appendix A (Glossary).

---

## 1. Motivation

### 1.1 The Core Challenge: Probability Density Function Estimation in High-Dimensional Spaces

In high-energy physics and detector calibration, we face a fundamental challenge: **estimating probability density functions (PDFs) and their statistical properties** (quantiles, moments, correlations) from data distributed across high-dimensional parameter spaces. This is not merely a function fitting problem—we must characterize the full statistical behavior of observables as they vary across multiple dimensions simultaneously.

**Note:** While examples in this specification are drawn from ALICE tracking and calibration (including TPC distortions, tracking performance, and combined detector calibration), the underlying statistical challenge—estimating local PDFs in high-dimensional sparse data—is generic to many scientific domains including medical imaging, climate modeling, and financial risk analysis.

**The statistical estimation problem:** Given measurements distributed in an *d*-dimensional binned space, we need to extract reliable statistical estimators (mean, median, RMS (Root Mean Square), MAD (Median Absolute Deviation), quantiles, higher moments) for each bin. However, as dimensionality increases, the **curse of dimensionality** manifests in two critical ways:

1. **Exponential sparsity:** With *n* bins per dimension, we face *n^d* total bins. Even with billions of events (e.g., ALICE collects 5×10^6 tracks/second × 10-15 hours = 180-270 billion tracks/day), many bins remain empty or contain insufficient statistics for reliable PDF characterization.

2. **Unbalanced distributions:** Physical observables often follow highly skewed distributions (exponential mass spectra, power-law transverse momentum), making naive sampling wasteful and leaving critical regions of parameter space under-represented.

**Example from ALICE TPC calibration:**
```
Spatial distortion map binning:
- 3D spatial bins: 152 (x) × 20 (y/x) × 28 (z/x) × 18 (sectors) = ~1.5M bins
- Time evolution: × 90 time slices = 135M total bins
- Target observables: dX, dY, dZ corrections (vector field)
- Even with 270 billion tracks/day, average statistics per bin: ~2000 events
- After quality cuts and balanced sampling: O(10-100) events per bin
```

**Example from performance parameterization:**
```
Track segment resolution as function of (pT, η, φ, occupancy, time):
- 5D parameter space: 50 × 40 × 36 × 20 × 100 = 144M bins
- Measurements: TPC-ITS track difference (bias and resolution),
                TPC-vertex (bias and resolution)
- Common approach: TPC-vertex and angular matching for QA parameterization
- Similar challenges: V0 reconstruction, PID (Particle IDentification) resolution
- Used for MC-to-data remapping and QA (Quality Assurance) variable calibration
```

For bins with <10 events, standard statistical estimators (mean, RMS) have large uncertainties, making robust PDF characterization impossible without additional assumptions.

**Figure 1: Sparse 3D Spatial Bins with ±1 Neighborhood Aggregation**
```
[Placeholder for figure showing:
 - 3D grid of spatial bins (xBin × y2xBin × z2xBin)
 - Center bin highlighted with sparse data (<10 events)
 - ±1 neighbors in each dimension (3×3×3 = 27 bins total)
 - Aggregated data providing sufficient statistics
 - Visual representation of local smoothness assumption]
```
*Figure to be added: Illustration of how sliding window aggregates sparse neighboring bins to enable reliable PDF estimation.*

### 1.2 The Local Smoothness Assumption and Functional Approximation

To overcome statistical sparsity, we must incorporate **prior knowledge** about the physical behavior of our observables. The fundamental assumption is **local smoothness**: physical quantities vary continuously in parameter space, exhibiting correlations between neighboring regions.

This assumption enables **functional approximation** through sliding window aggregation:

**Approach 1: Local constant approximation**  
Aggregate statistics from neighboring bins assuming the PDF properties are approximately constant within a local neighborhood:
$$\mu(\mathbf{x}_0) \approx \text{mean}\{y_i \mid \mathbf{x}_i \in \text{neighborhood}(\mathbf{x}_0)\}$$

**Approach 2: Weighted smoothing**  
Assign distance-based weights to neighbors, giving higher influence to bins closer to the center:
$$\mu(\mathbf{x}_0) \approx \frac{\sum_i w_i(\|\mathbf{x}_i - \mathbf{x}_0\|) \cdot y_i}{\sum_i w_i(\|\mathbf{x}_i - \mathbf{x}_0\|)}$$
where common weight functions include Gaussian: $w(d) = \exp(-d^2/\sigma^2)$ or inverse distance: $w(d) = 1/(1+d)$.

**Approach 3: Local kernel regression**  
Fit parametric functions (linear, polynomial) within the neighborhood, capturing local trends:
$$y(\mathbf{x}) \approx \beta_0 + \beta_1 \cdot (\mathbf{x} - \mathbf{x}_0) + \ldots \quad \text{within neighborhood}(\mathbf{x}_0)$$
where $\beta$ coefficients are fit using weighted least squares over the local window.

This sliding window methodology transforms the problem from:
- **"Estimate PDF at each isolated bin"** (fails in sparse regions)  
  to:
- **"Estimate smooth PDF field using local information"** (succeeds with local smoothness)

### 1.3 Beyond Simple Smoothing: PDF Estimation and Model Factorization

The sliding window approach serves a deeper purpose in the **RootInteractive** framework [[Ivanov et al. 2024, arXiv:2403.19330]](https://arxiv.org/abs/2403.19330): enabling iterative, multidimensional PDF estimation and analytical model validation.

#### 1.3.1 Balanced Semi-Stratified Sampling

To handle massive ALICE data volumes (>100TB/day) while maintaining statistical power across parameter space:

1. **Original data:** Highly unbalanced (exponential/power-law distributions in mass, pT, PID)
2. **Balanced sampling:** Pre-sample using **"balanced semi-stratified sampling"** (density-aware resampling that flattens highly imbalanced distributions such as pT or particle identification, enabling uniform coverage of the full parameter space)
3. **Volume reduction:** 10× to 10^4× reduction (typical: 10^2-10^3) depending on use case
    - Distortion maps: ~10× reduction (need high spatial statistics)
    - Performance parameterization: ~10^3× reduction (broader phase space coverage)
4. **Store weights:** Enable post-hoc reweighting to original distribution

**Example:** For track resolution studies across 5D phase space (pT, η, occupancy, time, PID), sampling from 10^11 tracks to 10^8 events provides sufficient statistics per bin while enabling interactive analysis with <4GB memory footprint.

**Note on sampling schemes:** For distortion map creation, uniform spatial sampling is under development; current production primarily uses time-based balanced sampling. For performance studies and particle identification, balanced sampling across kinematic variables is standard practice.

**Result:** Process 0.01-10% of data with full statistical coverage, enabling iterative analysis and rapid feedback cycles essential for calibration workflows.

#### 1.3.2 Functional Decomposition and Factorization

Real-world calibrations rarely have simple analytical models for full multidimensional behavior. However, we often have models for **normalized deltas** and **factorized components**.

**Example: TPC distortion modeling**
```
Full model (unknown): d(x, y, z, t, φ, rate, ...)
                      
Factorization approach:
1. Extract spatial base map: d₀(x, y, z) [from sliding window fits]
2. Model temporal delta: δd(t) = A·exp(-t/τ₁) + B·exp(-t/τ₂) [analytical]
   - Typical temporal resolution: 5-10 minute averaged maps (90 samples/day)
   - For fast fluctuations: O(1s) resolution requires coarser spatial binning
3. Exploit symmetry: φ-independence for space charge (electric charge accumulation from ionization) effects
4. Rate dependence: Normalize by IDC (Integrator Drift Current, a proxy for detector occupancy and space charge density)

Composed model: d(x,y,z,t,φ,rate) = d₀(x,y,z) · δd(t) · f(IDC) + symmetry checks
```

**Sliding window role:** Extract the non-parametric base functions (d₀) from sparse data, then validate factorization assumptions and fit parametric delta models on normalized residuals.

**Note on RootInteractive:** The RootInteractive tool [[Ivanov et al. 2024, arXiv:2403.19330]](https://arxiv.org/abs/2403.19330) provides interactive visualization and client-side analysis of the extracted aggregated data. Sliding window regression is the *server-side* preprocessing step that prepares binned statistics and fit parameters for subsequent interactive exploration and model validation.

#### 1.3.3 Symmetries, Invariants, and Alarm Systems

After normalization and factorization, physical symmetries should be restored:
- **Temporal invariance:** Corrections stable across runs (after rate normalization)
- **Spatial symmetry:** φ-independence for space charge effects
- **Magnetic field symmetry:** Consistent behavior for ±B fields

**Alarm logic:** If `(data - model) / σ > N` for expected symmetries, either:
- Data quality issue → flag for investigation
- Model inadequacy → symmetry-breaking effect discovered
- Calibration drift → update correction maps

**Sliding window enables:** Compute local statistics needed for σ estimation and symmetry validation across all dimensions.

### 1.4 The Software Engineering Challenge: A Generic Solution

While the statistical methodology is well-established (kernel regression, local polynomial smoothing), applying it to real-world detector calibration requires:

**Dimensional flexibility:**
- Integer bin indices (xBin, y2xBin, z2xBin)
- Float coordinates (time, momentum, angles)
- Mixed types in same analysis
- Dimensions ranging from 3D to 6D+ (typical use cases)
- **Note:** Actual dimensionality and bin counts depend on use case and memory constraints (e.g., Grid central productions have memory limits affecting maximum binning)

**Boundary conditions:**
- Spatial boundaries: mirror/truncate/extrapolate
- Periodic dimensions (φ angles): wrap-around
- Physical boundaries: zero padding
- Per-dimension configuration

**Integration with existing tools:**
- Must work with pandas DataFrames (standard scientific Python)
- Leverage existing groupby-regression engines (v4 with Numba JIT)
- Support pre-aggregated data from batch jobs
- Enable client-side interactive analysis (RootInteractive dashboards)

**Performance requirements:**
- Process 405k rows × 5 maps with ±1 window: <1 minute (typical TPC spatial case)
- Scale to 7M rows × 90 maps: <30 minutes (full temporal evolution)
- Memory efficient: avoid 27-125× expansion where possible; <4GB per session target
- Parallel execution across cores
- **Note:** Specific targets depend on use case, hardware, and dataset characteristics

**Reusability imperative:**
- One implementation for TPC distortions, particle ID, mass spectra, ...
- User-defined fit functions (linear, polynomial, non-linear, simple statistics)
- Configurable weighting schemes
- Documented, tested, maintainable

**Translating theory into practice:** Translating these statistical concepts into practice requires a software framework that maintains dimensional flexibility while remaining computationally efficient and memory-bounded (<4GB per analysis session). Past C++ and Python implementations demonstrated the value of this approach but had limitations in extensibility and performance (see Section 5 for detailed history). This specification defines requirements for a production-ready, general-purpose solution that addresses these limitations.

### 1.5 Scope and Goals of This Specification

This document defines a **Sliding Window GroupBy Regression** framework that:

1. **Supports arbitrary dimensionality** (3D-6D typical, extensible to higher)
2. **Handles mixed data types** (integer bins, float coordinates, categorical groups)
3. **Flexible window configuration** (per-dimension sizes, asymmetric, distance-based)
4. **Systematic boundary handling** (mirror, truncate, periodic, per-dimension rules)
5. **User-defined aggregations** (linear fits, statistics, custom functions)
6. **Performance at scale** (millions of rows, thousands of bins, <30 min runtime)
7. **Integration with RootInteractive** (pandas I/O, client-side visualization)
8. **Production-quality implementation** (tested, documented, maintainable)

**Primary use cases:**
- **ALICE TPC distortion maps:** Spatial corrections with temporal evolution
- **ALICE tracking performance:** Combined detector calibration and tracking quality
    - Track segment resolution: TPC-ITS, TPC-vertex matching (bias and resolution)
    - Angular matching and vertex constraints
    - V0 reconstruction resolution and biases
    - PID (Particle Identification) resolution and systematic uncertainties
    - Efficiency maps for various reconstruction algorithms
    - QA variables (χ², cluster counts, dE/dx) across parameter space
    - MC-to-data remapping corrections
- **Future development:** Combined tracking performance parameterization and ALICE calibration integration
- **Particle physics:** Invariant mass spectra in multi-dimensional kinematic bins
- **Generic:** Any binned analysis requiring PDF estimation in high dimensions (3D-6D+)

**Success criteria:**
- Replaces existing C++ implementations with cleaner API
- Enables new analyses previously infeasible (6D+ spaces)
- Reduces analysis time from hours/days to minutes
- Becomes standard tool in ALICE calibration workflow

**Intended audience:**
- ALICE tracking and calibration experts (primary: TPC, ITS, tracking performance)
- Particle physics data analysts (secondary)
- Scientific Python community (general reusability)

**Next steps:** Section 2 describes the representative datasets and validation scenarios that illustrate these concepts with concrete examples from ALICE TPC calibration and performance studies.

---

## 2. Example Data

This section describes representative datasets used to motivate and validate the sliding window regression framework. These examples span ALICE tracking, calibration, and performance studies, illustrating the range of dimensionalities, bin structures, and statistical challenges the framework must address.

### 2.1 Dataset Overview

Three primary dataset categories demonstrate the framework's applicability:

1. **TPC Spatial Distortion Maps** (current test data)
2. **TPC Temporal Evolution** (production scale)
3. **Tracking Performance Parameterization** (multi-dimensional)

Each dataset exhibits the characteristic challenges of high-dimensional sparse data requiring local aggregation through sliding window techniques.

---

### 2.2 Dataset A: TPC Spatial Distortion Maps (Test Data)

**Purpose:** Validate spatial sliding window aggregation with realistic detector calibration data.

**Data source:** ALICE TPC sector 3 distortion corrections from 5 time slices - example for distortion vs integrated digital current (IDC) calibration

#### 2.2.1 Structure

**File:** `tpc_realistic_test.parquet` (14 MB parquet for 1 sector - 5 maps/time slices for distortion vs current fits)

**Dimensions:**
```
Rows: 405,423
Columns: O(20)

Spatial binning:
- xBin:    152 bins [0 to 151]  (radial direction in TPC)
- y2xBin:   20 bins [0 to  19]  (pad-row normalized y)
- z2xBin:   28 bins [0 to  27]  (drift-direction normalized z)
- bsec:      1 value [3]         (sector 3 only in test data)


Temporal structure:
- run:            1 unique run
- medianTimeMS:   5 unique time points
- firstTFTime:    5 time slices
```

#### 2.2.2 Target Variables (Fit Targets)

**Distortion corrections (primary):**
- `dX`: Radial distortion [-4.4 to +5.0 cm]
- `dY`: Pad-row direction distortion [-1.4 to +2.0 cm]
- `dZ`: Drift direction distortion [-2.0 to +3.6 cm]

**Derived quantities:**
- `EXYCorr`: Combined XY correction magnitude [-0.84 to +0.89]
- `D3`: 3D distortion magnitude [0.23 to 4.85 cm]

All target variables are fully populated (405,423 non-null values).

#### 2.2.3 Features (Fit Predictors)

**Detector state:**
- `meanIDC`: Mean Integrator Drift Current [mean: 1.89, median: 1.97]
- `medianIDC`: Median IDC [mean: 1.89, median: 1.97]
- `deltaIDC`: IDC variation in respect to fill average 
- `meanCTP`, `medianCTP`: QA variable. -independent current proxy


**Statistics:**
- `entries`: Entries per bin [median: 2840]
- `weight`: Statistical weight

**Quality:**
- `flags`: Quality flags (value: 7 in test data)


**Memory footprint:** using per sector splitting
- In-memory (pandas): 45.6 MB
- Per-row overhead: 113 bytes

#### 2.2.5 Use Case

This dataset validates:
- **Spatial sliding window** aggregation (±1 in xBin, y2xBin, z2xBin)
- **Integer bin indexing** with boundary handling
- **Linear regression** within sliding windows (dX, dY, dZ ~ meanIDC)
- **Multi-target fitting** (simultaneous fits for dX, dY, dZ)


**Expected workflow:**
1. For each center bin (xBin, y2xBin, z2xBin)
2. Aggregate data from ±1 neighbors (3×3×3 = 27 bins)
3. Fit linear model: `dX ~ meanIDC` (and similarly for dY, dZ)
4. Extract coefficients, uncertainties, and diagnostics per center bin
5. Result: Smoothed distortion field with improved statistics

---


### 2.4 Dataset C: Tracking Performance Parameterization

**Purpose:** Multi-dimensional performance metrics requiring combined spatial, kinematic, and temporal aggregation.

#### 2.4.1 Track Segment Resolution
To provide comprehensive tracking performance characterization, 
we analyze track segment residuals and QA variables as functions of multiple kinematic and detector conditions.
Variables are usually transformed, e.g., instead of binning in pT we use q/pT for better linearity, and to minimize the number of bins
resp. to get enough statistics per bin.
**Measurement:** TPC-ITS matching and TPC-vertex constraints

**Dimensions:**
```
5D parameter space:
- q/Pt       200 bins [-8 to +8 c/GeV]   (charge over pT)
- η:         20 bins [-1.0 to +1.0]      (pseudorapidity)  
- φ:         180 bins [0 to 2π]           (azimuthal angle)
- sqrt(occupancy): -510 bins               (number of track in TPC volume)
- rate (kHz): 5-10 bins [0 to 50 kHz]      (detector load)

Total bins: 200 × 20 × 180 × 10 × 10 = 144,000,000

```

**Targets:**
- Track segment residuals: mean bias, RMS, quantiles (10%, 50%, 90%)
- Angular matching: Δθ, Δφ at vertex
- DCA (Distance of Closest Approach): XY and Z components
- χ² distributions per track type
- efficiency 
- PID- dEdx, dEdx per region and per specie




### 2.5 Dataset Comparison Summary

**Note:** Data volumes are approximate. Production analyses are typically limited by the **1 GB THN** (multidimensional histogram) size limit in ROOT.

| **Dataset** | **Dimensions** | **Bins** | **Rows (approx)** | **Memory** | **Sparsity** | **Window Type** |
|-------------|---------------|----------|-------------------|------------|--------------|-----------------|
| **A: TPC Spatial** | 3D (x,y,z) | 85k | 405k | 46 MB/sector | ~26% occupied | Integer ±1-2 |
| **C: Track Resolution** | 5D (q/pT,η,φ,occ,rate) | 7.2M | 1M-10M | 0.1-1 GB | 50-70% sparse | Float ±1-3 |

**Key observations:**
- **Dimensionality:** 3D to 5D in these examples (extensible to 6D+)
- **Bin counts:** 10⁴ to 10⁷ (memory and ROOT THN constraints)
- **Sparsity:** 26-70% of bins have insufficient individual statistics
- **Window types:** Integer (spatial bins), float (kinematic variables)
- **Memory range:** 50 MB (single sector) to 1 GB (full kinematic space)
- **Practical limits:** 1 GB THN size in ROOT constrains production binning

---

### 2.6 Data Characteristics Relevant to Sliding Window Design

#### 2.6.1 Bin Structure Types

**Observed in ALICE data:**

1. **Uniform integer grids** (TPC spatial bins)
   - Regular spacing, known bin IDs
   - Efficient neighbor lookup: bin ± 1, ± 2
   - Example: xBin ∈ [0, 151], step=1

2. **Non-uniform float coordinates** (kinematic variables, time)
   - Variable bin widths (e.g., q/pT transformation for linearity)
   - Neighbors defined by distance or bin index
   - Example: q/pT bins with non-uniform spacing for better statistics distribution

3. **Periodic dimensions** (φ angles)
   - Wrap-around at boundaries: φ=0 ≡ φ=2π
   - Requires special boundary handling

4. **Mixed types** (combined analyses)
   - Spatial (integer) + kinematic (float) + temporal (float)
   - Requires flexible window specification per dimension

#### 2.6.2 Statistical Properties

**From Dataset A analysis:**

```python
# Bin-level statistics (before sliding window):
entries_per_bin = [1, 1, 1, 2, 1, 1, ...]  # median: 1
mean_IDC = [1.89, 1.92, 1.88, ...]         # varies per bin
dX_values = [-2.1, 0.5, -1.8, ...]         # target distortions

# Challenge: Cannot reliably fit dX ~ meanIDC with n=1-2 points per bin
# Solution: Sliding window aggregates 27-125 neighbors → sufficient stats
```

**Statistical needs:**
- **Minimum for mean/median:** ~10 points (robust estimates)
- **Minimum for RMS/quantiles:** ~30 points (stable tail estimates)
- **Minimum for linear fit:** ~50 points (reliable slope, uncertainty)
- **Typical window provides:** 27 (±1 in 3D) to 343 (±3 in 3D) potential bins

**Reality check:** Not all neighbor bins are populated, effective N often 20-60% of theoretical maximum due to sparsity.

#### 2.6.3 Boundary Effects

**Spatial boundaries (TPC geometry):**
- xBin=0: Inner field cage (mirror or truncate)
- xBin=151: Outer field cage (mirror or truncate)
- z2xBin=0,27: Readout planes (asymmetric, truncate)
- 3 internal boundaries (stack edges at rows 63, 100, ...): no smoothing across boundaries
- φ: Periodic (wrap-around)


**Implications for sliding window:**
- Must support per-dimension boundary rules
- Cannot use one-size-fits-all approach
- Boundary bins have fewer neighbors → adjust weighting or normalization

---

### 2.7 Data Availability and Access for Benchmarking

**Test dataset (Dataset A):**
- File: `benchmarks/data/tpc_realistic_test.parquet` (14 MB)
- Format: Apache Parquet (optimized) or pickle (compatibility)
- Source: ALICE TPC sector 3, 5 time slices, anonymized for testing
- Public: Yes (within O2DPG repository for development and validation)


**Synthetic data generation:**
- For testing and benchmarking: Can generate representative synthetic data
- Preserves statistical structure without real detector specifics
- Script: `benchmarks/data/generate_synthetic_tpc_data.py` (to be added)

---

**Next steps:** Section 3 describes concrete use cases and workflows that leverage these datasets to demonstrate the sliding window framework's capabilities.

---

## 3. Example Use Cases

[To be written in next iteration]

---

## 4. Goal - Functional Representation

[To be written in next iteration]

---

## 5. Past Implementations

### 5.1 C++ Implementation (2015-2024)

**Overview:** The original sliding window implementation was developed in C++ within the ALICE AliRoot framework, 
using N-dimensional histograms as input structures. The code has not yet been ported to the Run 3 O2 framework, 
and until recently it was used for Run 3 data with AliRoot as a side package.

It was used for performance and dE/dx parameterisation, as well as the initial implementation of the TPC distortion 
maps in 2015. Q/q, track delta, and efficiency variables were grouped into histograms with the same binning. 
Several versions of binning with different granularity and focus were used, in order to bypass the ROOT internal 
limitation of 1 GB.

Detector-based summary binning versions:
* Kinematical variables (q/pt, tgl)
* ~ occupancy
* Phi/sector modulation (90 or 180 bins in the full phi range, or 10–20 bins per sector assuming sector symmetry)


**Key features:**
- Multi-dimensional histogram-based approach using ROOT's THnSparse (1 GB limit per histogram object)
  - O(10) variable types × 5 binning types used (see comment above)  
  - Aggregation using sampled data on server (bash parallel command), or farm if larger production
- Sliding window implementation as a preprocessing step together with groupby regression
  - Kernel-based neighbor aggregation using histogram bin indexing
  - In addition to calculating sliding window statistics (mean, median, std, mad, LTM) of variables of interest 
      (dE/dx, efficiency, track delta) also mean of variables used for binning (q/pT, eta, phi, occupancy)
  - Weighting schemes: uniform, distance-based (inverse distance, Gaussian)
- User-defined fit functions (linear, polynomial, custom)
- Integrated with ALICE offline analysis framework

#### 5.1 C++ Function Signature

```C++
/// Create list of histograms specified by selection
/// Should be rough equivalent of the "ALICE train" TTree->Draw();
///  a.) Data are read only once
///  b.) values expression are reused (evaluated only once)
///  c.) Axis labelling and names of variables extracted from the tree metadata (.AxisTitle)
/// * default cut
///   * default selection applied common for all histograms (can be empty)
///
/// * hisString : - semicolomn separated string
///   * his0;his1; ...; hisN
/// * histogram syntax:
///    * var0:var1:...:<#weight>>>hisName(bins0,min0,max0,bins1,min0,min, minValue,maxValue)
///    * Syntax:
///      * vari are histogramming expression
///      * weight (or cut) entry is optional
///        * default cut is always applied, weight is applied on top
///    * ranges syntax:
///      *  nbins,max,min where max and min are double or format strings
///        * in case format string % specified using (Fraction, mean,meanFraction, rms, rmsFraction)
///          *  %fraction.sigma
///          *  #cumulant
///          *  range for bin content can be specified in the same format (by default is not set)
/*!
##### CPU time to process one histogram or set of histograms (in particular case of esdTrack queries) is the same - and it is determined (90 %) by tree->GetEntry
\code
  THn * his0= (THn*)hisArray->At(0);
  his0->Projection(0)->Draw("");
  tree->SetLineColor(2);
  TStopwatch timer; tree->Draw("esdTrack.Pt()","(esdTrack.fFlags&0x40)>0&&esdTrack.fTPCncls>70","same",60000); timer.Print();
\endcode
*/

/// \param tree         - input tree
/// \param hisString    - selection string
/// \param defaultCut   - default selection applied common for all histograms (can be empty)
/// \param firstEntry   - first entry to process
/// \param lastEntry    - last entry to process
/// \param chunkSize    - chunk size
/// \param verbose      - verbosity
/// \return             - TObjArray of N-dimensional histograms
/*!
#### Example usage:
\code
    chunkSize=10000;
    verbose=7;
    chinput=gSystem->ExpandPathName("$NOTES/JIRA/PWGPP-227/data/2016/LHC16t/000267161/pass1_CENT_wSDD/filteredLocal.list");
    TString defaultCut="esdTrack.fTPCncls>70";
    TTree *tree=(TTree*)AliXRDPROOFtoolkit::MakeChain(chinput, "highPt", 0, 1000000000,0);
    TString hisString="";
    hisString+="esdTrack.Pt():#esdTrack.fTPCncls>70>>hisPtAll(100,0,30);";
    hisString+="esdTrack.GetAlpha():#esdTrack.fTPCncls>70>>hisAlpha(90,-3.2,3.2);";
    hisString+="esdTrack.GetTgl():#esdTrack.fTPCncls>70>>hisTgl(20,-1.2,1.2);";
    hisString+="esdTrack.Pt():esdTrack.GetAlpha():esdTrack.GetTgl():#esdTrack.fTPCncls>70>>hisPtPhiThetaAll(100,0,30,90,-3.2,3.2,20,-1.2,1.2);";
    hisString+="esdTrack.Pt():#(esdTrack.fFlags&0x4)>0>>hisPtITS(100,1,10);";
    hisString+="esdTrack.fIp.Pt():#(esdTrack.fFlags&0x4)>0>>hisPtTPCOnly(100,1,10);";
    TStopwatch timer; hisArray = AliTreePlayer::MakeHistograms(tree, hisString, "(esdTrack.fFlags&0x40)>0&&esdTrack.fTPCncls>70",0,60000,100000); timer.Print();
\endcode
 */
TObjArray  * AliTreePlayer::MakeHistograms(TTree * tree, TString hisString, TString defaultCut, Int_t firstEntry, Int_t lastEntry, Int_t chunkSize, Int_t verbose){
```
```C++
/// TStatToolkit::MakePDFMap function to calculate statistics from the N-dimensional PDF map
/// Original implementation - a copy of the MakeDistortionMapFast
/// \param histo              -  input n dimsnional histogram
/// \param pcstream           -  output stream to store tree with PDF statistic maps
/// \param projectionInfo     -
/// \param options            - option - parameterize statistic to extract
/// \param verbose            - verbosity of extraction
/// Example:
/// options["exportGraph"]="1";
///  options["exportGraphCumulative"]="1";
///  options["LTMestimators"]="0.6:0.5:0.4";
//  options["LTMFitRange"]="0.6:5:1";
void TStatToolkit::MakePDFMap(THnBase *histo, TTreeSRedirector *pcstream, TMatrixD &projectionInfo, std::map<std::string, std::string> pdfOptions, Int_t verbose)


```


**Strengths:**
- Proven in production for global tracking and calibration QA
- Computationally efficient for large datasets
- Well-tested and reliable
- Used for expert QAs

**Limitations:**
- Tight coupling with ROOT - adopting ROOT string-based configuration for describing histograms
- Using C++11 - not easy configuration - preferred not to rely on templates
- Rigid configuration: string-based API to define histograms and mapping (in Python using dictionaries)
- Limited extensibility: difficult to add new fit functions
- Relying on the AliRoot framework - not directly usable in O2 or scientific Python ecosystem




### 5.2 Python Implementation v1 (2024)

**Overview:** Initial Python prototype using DataFrame expansion to aggregate neighboring bins.

**Approach:**
```python
# For ±1 window in 3D:
# Replicate each row to all neighbor combinations
# (xBin±1) × (y2xBin±1) × (z2xBin±1) = 3³ = 27 copies per row
# Then use standard pandas groupby on expanded DataFrame
```

**Strengths:**
- Simple conceptual model
- Leverages existing pandas/numpy ecosystem
- Easy to prototype and modify
- Works with standard groupby-regression tools 

**Limitations:**
- **Memory explosion:** 27× expansion for ±1 window, 125× for ±2 window
- **Performance:** Slow for large datasets due to data replication overhead
- **Scalability:** Infeasible for ±3 windows (343×) or high-dimensional spaces
- Not production-ready for ALICE scale (7M rows × 90 maps × 27 = 17B rows)

### 5.3 Lessons Learned

**From C++ experience:**
- Kernel-based approaches are computationally efficient
- N-dimensional histogram indexing provides fast neighbor lookups
- Flexibility for user-defined fit functions is essential
- API complexity limits adoption and experimentation

**From Python v1 experience:**
- DataFrame-native approach integrates well with scientific Python ecosystem
- Expansion method is intuitive but not scalable
- Need balance between simplicity and performance

**Requirements for this specification:**
- Combine C++ performance with Python flexibility
- Efficient aggregation without full DataFrame expansion
- User-definable fit functions and weighting schemes
- Clean API accessible to non-experts
- Production-scale performance (<4GB memory, <30 min runtime)




## 6. Specifications - Requirements

This section defines the functional, interface, and performance requirements for the sliding window groupby regression framework. Requirements are extracted from the challenges and use cases described in Sections 1-2 and lessons learned from past implementations (Section 5).

---

### 6.1 Functional Requirements

#### 6.1.1 Core Capabilities

**FR-1: Multi-dimensional Sliding Window Aggregation**

The framework MUST support sliding window aggregation over arbitrary N-dimensional parameter spaces with the following characteristics:

- **Mixed coordinate types:** Integer bins (spatial grids) and float-valued coordinates (kinematic variables, time) within the same dataset
- **Per-dimension window specification:** Each dimension can have independent window size and boundary handling rules
- **Window sizes:** From ±1 (3 bins in 1D) to ±5 (11 bins in 1D), scalable to higher dimensions
- **Dimension count:** Support 3D to 6D spaces (extensible design for higher dimensions)

**FR-2: Local PDF Estimation and Statistical Aggregation**

For each center bin, the framework MUST compute statistical properties from aggregated neighbor data:

- **Basic statistics:** Mean, median, RMS, MAD (Median Absolute Deviation)
- **Quantiles:** User-specified quantiles (e.g., 10%, 25%, 50%, 75%, 90%)
- **Robust estimators:** LTM (Limited Trimmed Mean) with configurable fraction
- **Multi-target support:** Simultaneous computation for multiple target variables

**FR-3: Local Regression Within Windows**

The framework MUST perform regression analysis within each sliding window:

- **Linear models:** Support for multiple linear regression (multiple predictors, multiple targets)
- **Formula-based specification:** String-based formulas (e.g., `'dX ~ meanIDC + deltaIDC'`)
- **Custom fit functions:** User-defined callable functions for non-linear or specialized models
- **Multi-target fitting:** Simultaneous fitting of multiple dependent variables (e.g., dX, dY, dZ)
- **Diagnostics extraction:** R², residual statistics, coefficient uncertainties, p-values

**FR-4: Sparse Data Handling**

The framework MUST efficiently handle sparse high-dimensional data:

- **Empty bin tolerance:** Gracefully handle bins with zero entries
- **Minimum statistics enforcement:** Skip or flag bins with insufficient data for requested operation
- **Partial window aggregation:** Use available neighbors even if some bins are empty
- **Sparsity reporting:** Track effective sample size per aggregated window

---

#### 6.1.2 Data Input/Output Requirements

**FR-5: Input Data Format**

The framework MUST accept input data as:

- **Primary format:** pandas DataFrame or modin DataFrame (for distributed processing)
- **Required columns:**
  - Binning variables (group columns): Integer bin indices OR float coordinate values
  - Target variables: Quantities to fit or aggregate
  - Predictor variables: Features used in regression models
  - Optional: Statistical weights, quality flags, entry counts

**FR-6: Coordinate System Support**

The framework MUST support:

- **Integer bin coordinates:** Direct bin indexing (e.g., xBin=0 to 151)
- **Float coordinates:** Continuous values with binning inferred or specified
- **Transformed variables:** Variables pre-transformed for linearity (e.g., q/pT instead of pT)
- **Periodic dimensions:** Wrap-around coordinates (e.g., φ ∈ [0, 2π) wraps to 0)

**FR-7: Output Data Format**

The framework MUST produce output as:

- **Primary format:** pandas DataFrame with one row per center bin (group)
- **Output columns:**
  - Original binning columns (preserved)
  - Aggregated statistics (mean, median, RMS, etc.) per target variable
  - Fit coefficients and diagnostics (when regression performed)
  - Effective sample size (number of data points aggregated)
  - Quality flags or convergence indicators

**FR-8: RootInteractive Integration**

Output format MUST be compatible with RootInteractive visualization:

- Column naming conventions preserved
- Multi-dimensional results flattened appropriately
- Metadata for dimension specifications included

**FR-9: Error Handling and Validation**

The framework MUST implement robust error handling:

**Configuration validation:**
- Validate all window_spec entries have required fields ('size')
- Check boundary types are valid ('truncate', 'mirror', 'periodic')
- Verify weighting parameters consistent (e.g., 'gaussian' requires 'sigma')
- Raise `InvalidWindowSpec` exception for invalid configurations

**Data validation:**
- Check group_columns, fit_columns, predictor_columns exist in DataFrame
- Verify weights_column (if specified) exists and contains non-negative values
- Validate coordinate values are within reasonable ranges

**Numerical error handling:**
- **Singular matrix in fit:** Set coefficients and diagnostics to NaN, flag bin
- **Insufficient data:** Apply min_entries threshold, flag or skip bin
- **Overflow/underflow:** Handle gracefully, log warning

**Error categories:**
- **Fail-fast errors:** Invalid configuration, missing columns → raise exception immediately
- **Graceful degradation:** Numerical issues in individual bins → set NaN, continue processing
- **Warnings:** Sparse bins, unusual data distributions → log but continue

**Logging requirements:**
- `INFO`: Progress (N bins processed, M bins flagged)
- `WARNING`: Sparse bins, numerical instabilities
- `ERROR`: Configuration errors, missing data
- User-configurable verbosity level

**Performance warnings:**

The framework SHOULD issue performance-related warnings when suboptimal conditions are detected:

- **`PerformanceWarning`**: Issued when framework detects conditions that may impact performance
  
  **Examples:**
  - Dense-to-sparse mode switch: "Grid size exceeds max_dense_cells (50M), switching to sparse mode. Performance may be impacted for dense grids."
  - Excessive chunking: "Memory estimate requires 100+ chunks. Consider increasing memory_limit_gb or reducing window size."
  - Large window volume: "Window volume (27³ = 19,683 bins) is very large. Consider reducing window size for better performance."
  - Missing Numba: "Numba backend unavailable, falling back to NumPy. Expected 10-100× slowdown."
  
- **User control:**
  - Warnings can be suppressed via `warnings.filterwarnings('ignore', category=PerformanceWarning)`
  - Configurable via `performance_warnings: bool = True` parameter (future)
  
- **Logging integration:**
  - Performance warnings logged at `WARNING` level
  - Include actionable suggestions when possible (e.g., "Reduce window size or increase max_dense_cells")

**Example warning usage:**
```python
import warnings

class PerformanceWarning(UserWarning):
    """Warning for suboptimal performance conditions."""
    pass

# In framework code:
if total_cells > max_dense_cells:
    warnings.warn(
        f"Grid size ({total_cells:,} cells) exceeds max_dense_cells "
        f"({max_dense_cells:,}). Switching to sparse mode. "
        "Consider reducing window size for better performance.",
        PerformanceWarning
    )
```

---

### 6.2 API Design Requirements

#### 6.2.1 Main Interface Function

**API-1: Dictionary-Based Configuration**

The primary interface MUST use dictionary and list-based configuration (NO class-based config objects).

**Proposed function signature:**

```python
def make_sliding_window_fit(
    df: pd.DataFrame,
    group_columns: List[str],
    window_spec: Dict[str, Union[int, float, dict]],
    fit_columns: List[str],
    predictor_columns: List[str],
    fit_formula: Optional[Union[str, Callable]] = None,
    aggregation_functions: Optional[Dict[str, List[str]]] = None,
    weights_column: Optional[str] = None,
    binning_formulas: Optional[Dict[str, str]] = None,
    min_entries: int = 10,
    backend: str = 'numba',
    partition_strategy: Optional[dict] = None,
    **kwargs
) -> pd.DataFrame:
    """
    Perform sliding window regression and aggregation over multi-dimensional bins.
    
    Parameters
    ----------
    df : pd.DataFrame
        Input data with binning columns, targets, and predictors
    
    group_columns : List[str]
        Column names defining the binning dimensions (e.g., ['xBin', 'y2xBin', 'z2xBin'])
    
    window_spec : Dict[str, Union[int, float, dict]]
        Window specification for each dimension. Can be:
        - Simple: {'xBin': 2, 'y2xBin': 1}  # ±2, ±1 bins
        - Rich: {'xBin': {'size': 2, 'boundary': 'truncate'}, ...}
        See Section 6.2.2 for full specification format.
    
    fit_columns : List[str]
        Target variables to fit (dependent variables)
    
    predictor_columns : List[str]
        Feature variables used as predictors in regression
    
    fit_formula : Optional[Union[str, Callable]]
        Regression specification:
        - String formula: 'dX ~ meanIDC + deltaIDC' (statsmodels-like syntax)
        - Callable: custom_fit_func(X, y, weights) -> (coefficients, diagnostics)
        - None: aggregation only, no fitting
    
    aggregation_functions : Optional[Dict[str, List[str]]]
        Statistical aggregations to compute per target variable.
        Example: {'dX': ['mean', 'median', 'std', 'q10', 'q90'], 'dY': ['mean', 'rms']}
        Default: ['mean', 'std', 'entries'] for all fit_columns
    
    weights_column : Optional[str]
        Column name for statistical weights. If None (default), uniform weights (1.0) 
        are assumed for all data points. If specified, column must exist in df and 
        contain non-negative float values.
    
    binning_formulas : Optional[Dict[str, str]]
        Optional dictionary mapping coordinate names to binning formulas for reproducibility.
        Example: {'time': 'time / 0.5', 'pT': 'log10(pT) * 10'}
        These formulas document how float coordinates were binned to integers.
        Framework MAY use these for validation or metadata but does NOT apply them
        (user must pre-bin data before calling this function).
        Recommended for all analyses using formula-based binning (see DH-2).
    
    min_entries : int, default=10
        Minimum number of entries required in aggregated window to perform fit.
        Bins with fewer entries are flagged or skipped.
    
    backend : str, default='numba'
        Computation backend: 'numba' (JIT compiled) or 'numpy' (fallback)
    
    partition_strategy : Optional[dict]
        Memory-efficient partitioning configuration. See Section 6.4.2.
        Example: {'method': 'auto', 'memory_limit_gb': 4, 'overlap': 'full'}
    
    **kwargs
        Additional backend-specific options
    
    Returns
    -------
    pd.DataFrame
        Results with one row per center bin, containing aggregated statistics,
        fit coefficients, and diagnostics.
    """
```

---

#### 6.2.2 Window Specification Format

**API-2: Rich Window Specification with Defaults**

Window specifications MUST support both simple and rich formats with sensible defaults.

**Simple format (integer bins only):**
```python
window_spec = {
    'xBin': 2,        # ±2 bins in xBin dimension
    'y2xBin': 1,      # ±1 bin in y2xBin dimension
    'z2xBin': 1       # ±1 bin in z2xBin dimension
}
# Defaults: boundary='truncate', weighting='uniform'
```

**Rich format (full control):**
```python
window_spec = {
    'xBin': {
        'size': 2,               # ±2 bins
        'boundary': 'truncate',  # Options: 'truncate', 'mirror', 'periodic'
        'weighting': 'uniform'   # Options: 'uniform', 'distance', 'gaussian'
    },
    'timeBin': {
        'size': 3,               # ±3 bins (pre-binned from float time)
        'boundary': 'truncate',
        'binning_formula': 'time / 0.5',  # Optional: documents how float was binned
    },
    'pTBin': {
        'size': 1,               # ±1 bin (pre-binned from float pT)
        'boundary': 'truncate',
        'binning_formula': 'log10(pT) * 10',  # Optional: logarithmic binning
    },
    'phi': {
        'size': 10,              # ±10 degrees
        'boundary': 'periodic',  # Wrap around at 0/2π
        'weighting': 'gaussian',
        'sigma': 5.0,            # Gaussian width in same units as 'size'
        'binning_formula': 'phi * 180 / 3.14159'  # Optional: radians to degrees
    }
}
```

**Specification rules:**

1. **size (required):**
   - Integer bins: Integer value (±N bins)
   - Float coordinates: Float value (±X units)
   
2. **boundary (optional, default='truncate'):**
   - `'truncate'`: Use only available neighbors, no extension
   - `'mirror'`: Reflect bins at boundaries (e.g., bin -1 → bin 1)
   - `'periodic'`: Wrap around (e.g., for φ angles)

3. **weighting (optional, default='uniform'):**
   - `'uniform'`: All bins weighted equally
   - `'distance'`: Weight ∝ 1/(1 + distance) in bin index space
   - `'gaussian'`: Weight ∝ exp(-distance²/2σ²), requires 'sigma' parameter

4. **sigma (optional, required if weighting='gaussian'):**
   - Width parameter for Gaussian weighting, expressed in same units as 'size'
   - For integer bins: sigma in bin index units (e.g., sigma=1.5 means 1.5 bins)
   - For float coordinates: sigma in coordinate units (e.g., sigma=0.5 for pT in GeV/c)

5. **binning_formula (optional, metadata for reproducibility):**
   - String formula documenting how float coordinate was binned to integer
   - Uses pandas.eval() syntax (e.g., 'time / 0.5', 'log10(pT) * 10')
   - Framework MAY use this for validation or documentation
   - User MUST pre-bin data before calling framework (formula is metadata only)
   - Recommended for all pre-binned float coordinates to ensure reproducibility

---

#### 6.2.3 Fit Function Interface

**API-3: Dual Interface (String Formulas + Callables)**

The framework MUST support both string-based formulas and custom callable functions.

**String-based formulas (recommended for linear models):**

```python
# Simple linear regression
fit_formula = 'dX ~ meanIDC'

# Multiple predictors
fit_formula = 'dX ~ meanIDC + deltaIDC + meanCTP'

# Multiple targets (separate fits)
make_sliding_window_fit(
    df, 
    fit_columns=['dX', 'dY', 'dZ'],
    fit_formula='target ~ meanIDC + deltaIDC'
)
# Equivalent to:
#   dX ~ meanIDC + deltaIDC
#   dY ~ meanIDC + deltaIDC
#   dZ ~ meanIDC + deltaIDC
```

**Custom callable interface (for non-linear or specialized fits):**

```python
from typing import Dict, Tuple
import numpy as np

def custom_fit_function(
    X: np.ndarray,           # Predictor matrix (n_samples, n_features)
    y: np.ndarray,           # Target vector (n_samples,)
    weights: np.ndarray,     # Sample weights (n_samples,)
    **kwargs                 # Additional arguments
) -> Tuple[Dict[str, float], Dict[str, float]]:
    """
    Custom fit function signature.
    
    Note: If your model includes an intercept, X must explicitly include 
    an intercept column (column of ones). The framework does not automatically 
    add intercept terms.
    
    Returns
    -------
    coefficients : Dict[str, float]
        Fitted model parameters (e.g., {'intercept': 0.5, 'slope_meanIDC': 1.2})
    
    diagnostics : Dict[str, float]
        Fit quality metrics (e.g., {'r_squared': 0.95, 'rmse': 0.1, 'n_points': 150})
    """
    # User implementation here
    # Example: weighted linear fit (assumes X includes intercept column)
    coeffs = np.linalg.lstsq(X * weights[:, None], y * weights, rcond=None)[0]
    predictions = X @ coeffs
    residuals = y - predictions
    r_squared = 1 - np.sum(residuals**2) / np.sum((y - np.mean(y))**2)
    
    return (
        {'intercept': coeffs[0], 'slope_0': coeffs[1]},
        {'r_squared': r_squared, 'n_points': len(y)}
    )

# Usage
result = make_sliding_window_fit(
    df,
    fit_formula=custom_fit_function,
    # ... other params
)
```

**Requirements for custom functions:**

- MUST accept `X, y, weights` as first three positional arguments
- MUST return `(coefficients_dict, diagnostics_dict)` tuple
- MAY accept additional `**kwargs` for user options
- SHOULD be Numba-compatible for performance (if possible)

---

#### 6.2.4 Aggregation Function Specification

**API-4: Flexible Aggregation Configuration**

Users MUST be able to specify which statistical aggregations to compute.

**Default behavior (if aggregation_functions=None):**
```python
# Automatically compute for all fit_columns:
# - mean
# - std (standard deviation)
# - entries (sample count)
```

**Custom aggregations:**
```python
aggregation_functions = {
    'dX': ['mean', 'median', 'std', 'mad', 'q10', 'q50', 'q90'],
    'dY': ['mean', 'rms', 'ltm_0.6'],  # LTM with 60% fraction
    'meanIDC': ['mean', 'min', 'max']  # Aggregate predictors too
}
```

**Supported aggregation functions:**

| Function | Description | Output Column Name |
|----------|-------------|-------------------|
| `'mean'` | Arithmetic mean | `{column}_mean` |
| `'median'` | 50th percentile | `{column}_median` |
| `'std'` | Standard deviation | `{column}_std` |
| `'rms'` | Root mean square | `{column}_rms` |
| `'mad'` | Median absolute deviation | `{column}_mad` |
| `'min'`, `'max'` | Minimum, maximum | `{column}_min`, `{column}_max` |
| `'q{N}'` | N-th percentile | `{column}_q{N}` |
| `'ltm_{frac}'` | Limited trimmed mean | `{column}_ltm_{frac}` |
| `'entries'` | Sample count | `{column}_entries` |
| `'sum_weights'` | Sum of statistical weights | `{column}_sum_weights` |

**Note:** `sum_weights` is particularly important when using non-uniform weighting (`weights_column` is specified). It enables verification of effective weight used for mean/fit calculations and quality checks for weighted statistics.

---

### 6.3 Data Handling Requirements

#### 6.3.1 Coordinate System Handling

**DH-1: Integer Bin Indexing**

For integer bin coordinates:

- Bins MUST be identified by integer indices (0, 1, 2, ...)
- Neighbor lookup MUST use integer arithmetic (center ± window_size)
- Boundary handling MUST respect bin index limits

**DH-2: Float Coordinate Handling**

The framework operates on integer bin coordinates. For float-valued coordinates, users MUST pre-bin data into integer bins before calling the framework.

**Recommended: Formula-based binning**

Users SHOULD specify binning as string formulas that can be evaluated, stored, and reproduced:

```python
# Define binning formulas (part of analysis configuration)
binning_formulas = {
    'time': 'time / 0.5',              # Uniform bins (0.5 unit width)
    'pT': 'log10(pT) * 10',            # Logarithmic bins
    'eta': '(eta + 1.5) * 20',         # Shifted and scaled
    'phi': 'phi * 180 / 3.14159'       # Radians to degrees × bin scale
}

# Apply binning using df.eval() for reproducibility
for coord, formula in binning_formulas.items():
    df[f'{coord}Bin'] = df.eval(formula).astype(int)

# Framework operates on integer bins
result = make_sliding_window_fit(
    df,
    group_columns=['xBin', 'timeBin', 'pTBin'],
    window_spec={'xBin': 2, 'timeBin': 3, 'pTBin': 1},
    ...
)
```

**Benefits of formula-based binning:**
- Reproducibility: Formula can be stored in configuration/metadata
- Flexibility: Supports uniform, logarithmic, custom transformations
- Consistency: Same formula pattern used for fits (string formulas + callables)
- Traceability: Analysis pipeline includes binning specification

**Alternative: Direct Python expression** (for simple cases)

For quick interactive analysis, direct Python expressions MAY be used:

```python
# Quick one-liner for simple uniform binning
df['timeBin'] = (df['time'] / 0.5).astype(int)
```

**Binning formula validation:**

When using formula-based binning, the following validation rules apply:

- **Expression MUST evaluate to numeric:** Formula must produce a pandas Series with numeric dtype (int or float)
- **Result MUST be finite:** No NaN, inf, or -inf values allowed after evaluation
- **Convertible to integer:** Result must be safely convertible to int32 or int64 without critical loss of information
- **Invalid syntax handling:** Invalid formula syntax → raise `InvalidWindowSpec` exception with clear error message
- **Explicit rounding:** Users SHOULD use `round()`, `floor()`, or `ceil()` in formula for explicit control over float-to-int conversion
- **Range validation:** Framework MAY validate that bin indices are within reasonable range (e.g., 0 to 10^6)

**Example with explicit rounding:**
```python
binning_formulas = {
    'time': 'floor(time / 0.5)',           # Explicit floor
    'pT': 'round(log10(pT) * 10)',         # Explicit rounding
    'eta': 'floor((eta + 1.5) * 20)'       # Explicit floor
}
```

**Error handling:**
```python
try:
    df['timeBin'] = df.eval(binning_formula).astype(int)
except (SyntaxError, KeyError) as e:
    raise InvalidWindowSpec(f"Invalid binning formula: {e}")
except (ValueError, TypeError) as e:
    raise InvalidWindowSpec(f"Formula result not convertible to integer: {e}")
```

**Requirements:**
- Framework MUST accept integer bin coordinates (after user bins floats)
- Binning formulas SHOULD be stored with analysis configuration for reproducibility
- Framework MAY accept binning formulas as metadata (window_spec enrichment, see API-2)
- Mixed coordinate types supported: some pre-binned integers, others floats (if discrete centers)

**For irregular/observed grids** (Alternative workflow):

If data has discrete float coordinate values (e.g., observed measurement points):
- Framework treats each unique float value as a center bin
- Window size specified in coordinate units (e.g., ±0.5 GeV/c)
- Neighbor identification by distance calculation
- This approach is LESS efficient than pre-binning and NOT recommended for regular grids

**Recommended workflow:**
1. **Regular grids** (most common): Pre-bin floats → integers using formulas (Approach 1)
2. **Irregular grids** (rare): Use observed float values as centers (Approach 2)

**Note:** Approach 1 (formula-based pre-binning) is strongly recommended for:
- Performance: Enables efficient integer arithmetic in zero-copy accumulator (MEM-3)
- Clarity: Grid structure is explicit
- Reproducibility: Binning formula is part of configuration

**DH-3: Transformed Variables**

The framework MUST support pre-transformed variables:

- User transforms data before input (e.g., compute q/pT from pT and charge)
- Framework treats transformed variables as regular coordinates
- No automatic transformation or inverse transformation
- Documentation MUST provide guidance on when/why to transform (linearity, bin homogeneity)

**DH-4: Periodic Dimensions**

For periodic coordinates (e.g., azimuthal angle φ):

- When `boundary='periodic'` specified:
  - Bins at φ ≈ 0 and φ ≈ 2π are neighbors
  - Distance calculation wraps around period
  - Window aggregation crosses boundary seamlessly
- User MUST specify periodicity via `boundary='periodic'` in window_spec
- Framework MUST validate periodic dimension ranges

---

#### 6.3.2 Boundary Condition Handling

**DH-5: Boundary Strategies**

The framework MUST implement the following boundary handling modes:

**Truncate (default):**
- Use only bins that exist within valid range
- Bins near boundaries have asymmetric windows
- Effective window size varies near edges
- **Use case:** Physical boundaries (detector edges)

**Mirror:**
- Reflect bin indices at boundary
- Example: For boundary at 0, bin -1 → bin 1, bin -2 → bin 2
- Symmetric windows preserved
- **Use case:** Symmetric physical systems

**Periodic:**
- Wrap around at boundaries
- Example: For φ ∈ [0, 2π), φ = 2π + ε → φ = ε
- Full window size maintained
- **Use case:** Cyclic coordinates (angles)

**DH-6: Multiple Boundary Types in Single Dataset**

The framework MUST support different boundary rules for different dimensions simultaneously:

```python
window_spec = {
    'xBin': {'size': 2, 'boundary': 'truncate'},    # Detector edge
    'y2xBin': {'size': 1, 'boundary': 'mirror'},    # Symmetric system
    'phi': {'size': 10, 'boundary': 'periodic'}     # Azimuthal angle
}
```

---

#### 6.3.3 Missing Data and Sparsity

**DH-7: Empty Bin Handling**

The framework MUST handle bins with no data:

- Empty bins are skipped during aggregation
- Effective sample size reported for each aggregated window
- If center bin is empty but neighbors exist: optionally interpolate or flag
- User-configurable behavior via `handle_empty_bins` parameter

**DH-8: Minimum Statistics Enforcement**

The framework MUST enforce minimum sample size requirements:

- Parameter: `min_entries` (default: 10)
- Bins with `n < min_entries` after aggregation are:
  - Flagged in output (e.g., `quality_flag = 'insufficient_stats'`)
  - Optionally skipped (fit not performed)
  - Diagnostics set to NaN or special value
- User can query/filter results based on flags

**Quality metrics for sparse windows:**

The framework MUST track and report window completeness:
- `effective_window_fraction = n_valid_neighbors / n_expected_neighbors`
- Where:
  - `n_valid_neighbors` = number of neighbor bins with data
  - `n_expected_neighbors` = total window volume (e.g., 27 for ±1 in 3D)
- Output column: `{center}_window_fraction` (float 0.0-1.0)
- Enables users to identify and filter results from highly sparse regions

**Example:**
```python
# ±1 window in 3D expects 27 neighbors (3³)
# If only 15 bins have data:
effective_window_fraction = 15 / 27 = 0.556
```

---

### 6.4 Performance and Memory Requirements

#### 6.4.1 Performance Targets

**PERF-1: Runtime Performance**

The framework MUST meet the following performance targets:

- **Small datasets** (< 1M rows, 3D): < 1 minute
- **Medium datasets** (1-10M rows, 4D): < 10 minutes
- **Large datasets** (10-100M rows, 5D): < 30 minutes (with partitioning)
- **Benchmark:** 405k rows × 27 neighbors (±1 in 3D) should complete in < 2 minutes

Performance MUST be measured on reference hardware:
- Consumer laptop (8-core, 16GB RAM) for small/medium
- Workstation (16-core, 64GB RAM) for large

**PERF-2: Scalability**

The framework MUST scale efficiently with:

- **Number of dimensions:** Near-linear scaling (2× dimensions ≈ 2-3× runtime)
- **Window size:** Polynomial scaling with window volume (expected)
- **Number of targets:** Linear scaling (2× targets ≈ 2× runtime for independent fits)

**PERF-3: Backend Performance**

- **Numba backend** (primary): MUST achieve 10-100× speedup over naive pandas implementation
- **NumPy backend** (fallback): MUST provide correct results, performance secondary
- Users can benchmark both backends via `backend` parameter

---

#### 6.4.2 Memory Management

**MEM-1: Memory Limits**

The framework MUST operate within typical production constraints:

- **Target:** < 4 GB RAM for medium datasets (5-10M rows)
- **Maximum:** < 16 GB RAM for large datasets (with partitioning)
- **Avoid:** Memory explosion from DataFrame expansion (Python v1 issue)

**MEM-2: Zero-Copy Aggregation**

The framework MUST use in-place aggregation strategies:

- NO full DataFrame replication or expansion
- Aggregation performed on views or index slices where possible
- Temporary buffers reused across windows
- NumPy/Numba array operations preferred over pandas

**MEM-3: Zero-Copy Accumulator Strategy**

The framework MUST implement a zero-copy accumulator-based algorithm to achieve O(#centers) memory complexity instead of O(N × window_volume).

**Core principle:**
- **NO materialization** of the exploded neighbor table (DataFrame expansion)
- **Direct accumulation:** For each data point, update statistics for all affected neighbor centers
- **Memory scales with output size**, not input × window volume

**Algorithmic requirements:**

1. **Accumulator state per center:**
   The framework MUST track sufficient statistics for each center bin:
   - `count`: Number of data points aggregated (int64)
   - `sum_w`: Sum of statistical weights (float64)
   - `sum_wy`: Sum of weighted values (float64)
   - `sum_wy2`: Sum of weighted squared values (float64)
   
   Additional statistics (e.g., for regression) MAY extend this to include:
   - `sum_wX`: Sum of weighted predictors (for linear regression)
   - `sum_wXX`: Sum of weighted predictor products (for OLS matrices)
   - `sum_wXy`: Sum of weighted predictor × target products

2. **Dense vs Sparse mode selection:**
   The framework MUST automatically select between dense and sparse accumulators based on grid size:
   
   **Dense mode** (faster, used when memory predictable):
   - Allocate flat NumPy arrays of size `prod(axis_sizes)` for each statistic
   - Use when: `prod(axis_sizes) ≤ max_dense_cells` (default: 50,000,000 cells)
   - Memory: `3 × 8 bytes × prod(axis_sizes)` (for count, sum_wy, sum_wy2)
   - Access: O(1) array indexing via packed linear codes
   
   **Sparse mode** (scales to huge grids):
   - Use hash map (e.g., Numba typed.Dict or equivalent)
   - Store only touched centers: `dict[center_code] = (count, sum_w, sum_wy, sum_wy2)`
   - Memory: `~40-80 bytes × #touched_centers`
   - Access: O(1) hash lookup
   
   **Selection criterion:**
   ```python
   total_cells = np.prod([hi[d] - lo[d] + 1 for d in range(D)])
   use_dense = (total_cells <= max_dense_cells)
   ```

3. **Linear index packing:**
   Multi-dimensional center coordinates MUST be packed into linear indices for efficient storage:
   ```python
   # Compute strides for row-major ordering
   strides[d] = prod(sizes[d+1:])
   
   # Pack coordinates to linear index
   linear_index = sum(coords[d] * strides[d] for d in range(D))
   ```

4. **Accumulation loop structure:**
   For each data point `(x, y, w)` in input:
   ```
   For each neighbor offset in window:
       center_coords = x + offset
       Apply boundary handling (truncate/mirror/periodic)
       If center valid:
           Pack center_coords → linear_index
           Update accumulator[linear_index]:
               count += 1
               sum_w += w
               sum_wy += w * y
               sum_wy2 += w * y * y
   ```

5. **Chunking for cache locality:**
   The framework SHOULD process data in chunks (default: 1,000,000 rows) to:
   - Improve CPU cache performance
   - Enable map-reduce parallelization
   - Limit temporary memory overhead
   
   **Map-reduce pattern:**
   - **Map:** Each chunk produces local accumulators (dense arrays or sparse dict)
   - **Reduce:** Merge accumulators across chunks:
     - Dense: element-wise array addition
     - Sparse: hash map merge (sum values for common keys)

6. **Memory estimation formula:**
   The framework MUST provide memory estimation before execution:
   
   **Dense mode:**
   ```
   memory_MB = (n_statistics × 8 bytes × prod(axis_sizes)) / 1e6
   where n_statistics = 3 (base) + extras for regression
   ```
   
   **Sparse mode:**
   ```
   memory_MB = (80 bytes × estimated_touched_centers) / 1e6
   where estimated_touched_centers ≤ min(N, prod(axis_sizes))
   ```
   
   **Data chunks:**
   ```
   chunk_memory_MB = (chunksize × n_columns × 8 bytes) / 1e6
   ```
   
   **Total estimate:**
   ```
   total_memory = accumulator_memory + chunk_memory + overhead (×1.2 safety factor)
   ```

7. **Boundary handling in accumulation kernel:**
   Boundary policies (truncate, mirror, periodic) MUST be applied during neighbor enumeration:
   ```python
   for offset in window_offsets:
       neighbor_coord = center_coord + offset
       valid_coord, is_valid = apply_boundary(neighbor_coord, boundary_mode, lo, hi)
       if is_valid:
           update_accumulator(valid_coord, value, weight)
   ```

8. **Output decoding:**
   After accumulation, the framework MUST:
   - Identify non-zero centers (dense: np.nonzero, sparse: dict.keys())
   - Decode linear indices back to multi-dimensional coordinates
   - Compute final statistics from accumulators:
     ```
     mean = sum_wy / sum_w
     var = (sum_wy2 / sum_w) - mean²
     std = sqrt(var × n/(n-1))  # Bessel correction if n > 1
     ```
   - Return as DataFrame with one row per center

**Implementation notes:**

- **Numba JIT compilation:** Zero-copy kernels SHOULD use Numba @njit for 10-100× speedup
- **Parallel execution:** Map phase MAY use ProcessPoolExecutor for multi-core scaling
- **No shared state:** Each chunk/process operates independently until reduce phase
- **Deterministic results:** Accumulation order must not affect final statistics (associative operations only)

**Validation requirements:**

- Framework MUST verify that zero-copy results match naive DataFrame explosion (on small test data)
- Memory profiling MUST confirm O(#centers) scaling, not O(N × E)
- Performance tests MUST show expected speedup vs pandas groupby + explode approach

**Reference implementation:**

A reference Numba-based implementation following this specification is available, demonstrating:
- Dense and sparse accumulator modes
- Boundary handling (truncate/mirror/periodic)
- Chunk-based processing
- Linear index packing/unpacking
- Memory estimation

---

**MEM-4: Data Partitioning** (Optional, for datasets > memory limit)

For datasets where even zero-copy accumulators exceed memory (e.g., 7D grids with billions of centers), the framework MAY implement spatial partitioning:

**Partition strategy configuration:**
```python
partition_strategy = {
    'method': 'auto',           # 'auto', 'manual', 'none'
    'memory_limit_gb': 4,       # Target memory budget
    'overlap': 'full',          # 'full', 'minimal'
    'partition_columns': None,  # Auto-detect or user-specified
}
```

**Partitioning approach:**

1. **Spatial tiling:**
   - Divide coordinate space into tiles (e.g., partition along first dimension)
   - Each tile is processed independently with zero-copy accumulators
   - Tiles overlap by window size to ensure correct neighbor aggregation

2. **Overlap handling:**
   - `'full'`: Overlap = window_size in all dimensions
   - `'minimal'`: Overlap = window_size only in partitioned dimension(s)
   
   Example for 3D space partitioned along x:
   ```
   Partition 1: x ∈ [0, 50]   with overlap [48, 52]
   Partition 2: x ∈ [48, 100] with overlap [96, 100]
   ```

3. **Result deduplication:**
   - Each center bin appears in only ONE partition's final output
   - Rule: Keep result from partition where center is NOT in overlap region
   - If center in multiple overlaps: use deterministic tie-breaking (e.g., lowest partition ID)

4. **Memory validation:**
   - Before partitioning, estimate memory per partition using MEM-3 formulas
   - Adjust partition size if estimate exceeds memory_limit_gb
   - Fail gracefully if single partition still exceeds limit

**Note:** For most ALICE use cases (3-5D, < 10M centers), zero-copy accumulators without partitioning are sufficient. Partitioning is primarily for future 6-7D applications or real-time processing constraints.

---

### 6.5 Integration Requirements

#### 6.5.1 Existing Framework Integration

**INT-1: GroupBy Regression v4 Compatibility**

The sliding window framework MUST integrate with existing groupby-regression v4:

- Use v4's Numba kernel infrastructure where applicable
- Reuse v4's fit function implementations (linear regression, diagnostics)
- Support v4's output format conventions
- NO duplication of core regression logic

**INT-2: RootInteractive Output Format**

Output DataFrames MUST be compatible with RootInteractive:

- Column naming: `{variable}_{statistic}` (e.g., `dX_mean`, `dX_std`)
- Fit coefficients: `coef_{predictor}_for_{target}` (e.g., `coef_meanIDC_for_dX`)
- Metadata columns: `entries`, `quality_flag`, `effective_window_size`
- Multi-dimensional results: Flatten hierarchical results into single DataFrame

**INT-3: Modin Support (Future)**

The framework SHOULD be designed for future modin integration:

- API MUST be compatible with modin DataFrame (same as pandas)
- Backend implementation MAY use modin's parallel groupby when available
- Initial implementation: pandas only, modin as stretch goal
- **Compatibility requirement:** Framework MUST NOT depend on pandas internals that break modin compatibility (e.g., direct access to `_data`, `BlockManager`, or non-public APIs)

---

#### 6.5.2 Workflow Integration

**INT-4: Pipeline Compatibility**

The framework MUST fit into ALICE calibration pipelines:

- **Input:** Read from parquet, ROOT, or pickle formats
- **Output:** Write to parquet (primary) or ROOT (via uproot)
- **Chaining:** Output can be input to subsequent processing steps
- **Batch processing:** Support processing multiple files/runs

**INT-5: Grid Production Compatibility**

The framework MUST support ALICE Grid central productions:

- Memory limits: < 4 GB per job (enforced via partitioning)
- No external dependencies beyond: pandas, numpy, numba, scipy
- Deterministic results (same input → same output)
- Error handling: Graceful failure with clear error messages

---

### 6.6 Testing and Validation Requirements

#### 6.6.1 Correctness Validation

**TEST-1: Reference Implementation Tests**

The framework MUST pass validation against reference implementations:

- **Test dataset:** `tpc_realistic_test.parquet` (405k rows, 3D spatial)
- **Reference:** Manual sliding window aggregation (slow but verified correct)
- **Tolerance:** Numerical differences < 1e-7 for aggregations, < 1e-5 for fit coefficients

**TEST-2: Edge Case Tests**

The framework MUST correctly handle:

- Empty bins (no data in center or neighbors)
- Single data point in window
- All neighbors empty (isolated bin)
- Boundary bins (different window sizes)
- Periodic boundary wrap-around
- Highly sparse data (< 10% occupancy)

**TEST-3: Boundary Condition Tests**

Verify correct behavior for each boundary type:

- Truncate: Asymmetric windows near edges
- Mirror: Symmetric windows preserved
- Periodic: Wrap-around correctness
- Mixed boundaries: Different rules per dimension

---

#### 6.6.2 Performance Benchmarks

**TEST-4: Runtime Benchmarks**

Required benchmark scenarios:

1. **Small dataset:** 100k rows, 3D (xBin, y2xBin, z2xBin), ±1 window
2. **Medium dataset:** 1M rows, 4D (+ time), ±2 window
3. **Large dataset:** 10M rows, 5D (+ occupancy), ±1 window
4. **Scaling test:** Vary window size (±1, ±2, ±3) on fixed dataset

Report:
- Runtime (seconds)
- Memory peak (GB)
- Groups/second throughput
- Speedup vs naive implementation

**TEST-5: Memory Benchmarks**

Track memory usage:

- Peak memory during execution
- Memory per row processed
- Partition overhead (if applicable)
- Memory scaling with window size

---

#### 6.6.3 Integration Tests

**TEST-6: End-to-End Workflow**

Test complete workflow from raw data to RootInteractive:

1. Load TPC distortion data (parquet)
2. Apply sliding window regression (±1 in 3D)
3. Fit dX, dY, dZ ~ meanIDC
4. Export to parquet
5. Verify RootInteractive can load and visualize

**TEST-7: Reproducibility**

Verify deterministic behavior:

- Same input data + same parameters → identical output
- Test across different runs, machines
- Document any non-deterministic aspects (e.g., floating point accumulation order)

**TEST-8: Visual Validation**

The framework SHOULD support visual quality assurance:

**Purpose:** Verify smoothness and continuity of sliding window results

**Requirements:**
- Generate 1D slices through multi-dimensional results (e.g., fix y, z → plot dX vs x)
- Create 2D heatmaps for selected dimension pairs
- Overlay raw data points with smoothed results
- Highlight bins flagged for insufficient statistics or poor fit quality

**Validation checks:**
- Smoothness: No discontinuities or artifacts in fitted surfaces
- Consistency: Nearby bins show similar values (unless data shows true discontinuity)
- Coverage: Visual confirmation of which regions have sufficient data
- Boundary handling: Verify truncate/mirror/periodic modes work correctly at edges

**Output format:**
- PNG/PDF plots for documentation
- Interactive HTML dashboards (e.g., via RootInteractive)
- Automated pass/fail criteria for obvious issues (e.g., NaN islands, discontinuities > N×σ)

**Example tests:**
```python
# Test 1: 1D slice of TPC distortion map
plot_slice_1d(results, dimension='xBin', fixed_values={'y2xBin': 0, 'z2xBin': 14})

# Test 2: 2D heatmap
plot_heatmap_2d(results, dimensions=('xBin', 'z2xBin'), fixed_values={'y2xBin': 0})

# Test 3: Compare raw vs smoothed
plot_comparison(df_raw, results_smoothed, variable='dX')
```

---

### 6.7 Documentation Requirements

**DOC-1: API Documentation**

Complete docstrings for all public functions:

- Function purpose and use cases
- All parameters with types and defaults
- Return value specification
- Examples for common use cases
- Links to relevant specification sections

**DOC-2: User Guide**

Comprehensive guide covering:

- Quick start examples (simple use cases)
- Window specification guide (all boundary types)
- Custom fit function tutorial
- Performance optimization tips
- Troubleshooting common issues

**DOC-3: Specification Compliance**

Implementation MUST reference this specification:

- Map implementation modules to specification sections
- Document deviations or extensions
- Track requirements coverage in test suite

---

### 6.8 Non-Requirements (Out of Scope)

For clarity, the following are explicitly OUT OF SCOPE for initial implementation:

**NS-1: Automatic variable transformation**
- Users must pre-transform variables (e.g., compute q/pT)
- Framework does not auto-detect or suggest transformations

**NS-2: Adaptive window sizing**
- Window sizes are fixed, not data-driven
- Future work: Could adapt based on local density

**NS-3: Multi-resolution hierarchical windows**
- One window size per dimension
- No hierarchical or pyramid structures

**NS-4: Real-time processing**
- Designed for batch/offline processing
- Online streaming not supported

**NS-5: GPU acceleration**
- Initial implementation: CPU only (Numba)
- GPU support is future work

**NS-6: Distributed computing beyond modin**
- No Dask, Spark, or Ray integration
- Partitioning is local memory management, not distributed

**NS-7: 'Extend' boundary mode**
- Boundary extrapolation (using nearest valid bin for out-of-range neighbors) is OUT OF SCOPE
- This mode introduces data imputation bias and violates the principle of no implicit extrapolation
- Only 'truncate', 'mirror', and 'periodic' boundary modes are supported
- Rationale: Users requiring edge extrapolation should apply explicit preprocessing

---

## Summary of Key Requirements

| Category | Key Requirements |
|----------|------------------|
| **Functional** | Multi-dimensional windows, PDF estimation, local regression, sparse data |
| **API** | Dictionary config, rich window specs, string + callable fits |
| **Data** | Integer/float coords, transformed variables, periodic dimensions |
| **Performance** | < 30 min for 10M rows, < 4 GB memory, 10-100× speedup with Numba |
| **Integration** | GroupBy v4, RootInteractive, ALICE Grid, pandas/modin |
| **Testing** | Correctness vs reference, edge cases, benchmarks, reproducibility |

---

**Next Steps:** Section 6 draft complete. Ready for review by MI, GPT, and Gemini. Implementation can begin once specification is approved.

---

## References

- Ivanov, M., Ivanov, M., Eulisse, G. (2024). "RootInteractive tool for multidimensional statistical analysis, machine learning and analytical model validation." arXiv:2403.19330v1 [hep-ex]
- [ALICE TPC references to be added]
- [Statistical smoothing references to be added]

---

## Appendix A: Glossary of ALICE-Specific Terms

This specification uses terminology from the ALICE experiment at CERN and the ROOT data analysis framework. For readers outside the ALICE collaboration, key terms are defined below:

**ALICE:** A Large Ion Collider Experiment at CERN's Large Hadron Collider (LHC), specializing in heavy-ion physics and quark-gluon plasma studies.

**AliRoot:** Legacy ALICE offline analysis framework (C++03, ~2000-present), tightly integrated with ROOT and GEANT3. Used for data processing and physics analysis during LHC Run 1 and Run 2. Still used for historical data analysis, being phased out in favor of O2 for new production.

**O2:** ALICE Run 3 analysis framework (modern C++17, 2022+), successor to AliRoot with improved performance, memory efficiency, and maintainability. Built on FairRoot and Data Processing Layer (DPL). Designed for the high-luminosity Run 3 data-taking period with continuous readout.

**TPC (Time Projection Chamber):** ALICE's main tracking detector. A large cylindrical gas detector that reconstructs charged particle trajectories in three dimensions by measuring ionization electrons drifting in an electric field. Covers pseudorapidity range |η| < 0.9, providing up to 159 space points per track.

**THnSparse:** ROOT class for N-dimensional sparse histograms. Stores only populated bins to save memory, limited to ~2³¹ bins (~1 GB typical practical limit due to ROOT's internal 32-bit indexing). Used extensively in ALICE for multi-dimensional performance and calibration studies.

**TTree:** ROOT's columnar data structure for storing event-based analysis data. Similar conceptually to Apache Parquet or HDF5, but with C++ tight integration and high-energy physics conventions. Supports compression and lazy branch loading for selective access.

**dE/dx (energy loss per unit length):** Ionization energy deposited by a charged particle per unit path length in the TPC gas. Primary observable for particle identification (π/K/p/e⁻ separation) via the Bethe-Bloch formula.

**Distortion maps:** 3D vector fields describing systematic track reconstruction errors in the TPC due to space charge effects, E×B effects, and field inhomogeneities. Derived from comparison of reconstructed and true (Monte Carlo or reference) track positions. Calibrated using sliding window regression over spatial and temporal bins.

**ROOT:** CERN's C++ framework for data analysis in high-energy physics. Provides histograms (TH1, THnSparse), trees (TTree), fitting (TF1), and I/O. Standard tool in particle physics but has performance limitations for multi-TB scale datasets typical of Run 3.

**Run 3:** ALICE data-taking period starting 2022, with Pb-Pb collision rates 50× higher than Run 2 and continuous readout (50 kHz Pb-Pb, up to 500 kHz pp), requiring new frameworks and analysis techniques.

---

**End of Section 1 Draft**