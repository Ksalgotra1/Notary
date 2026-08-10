import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  Shield,
  BookOpen,
  Award,
  ShieldCheck,
  Key,
  FileCheck,
  Lock,
  Scale,
  SearchCheck,
  Layers,
  Cpu,
  Database,
  GitCommit,
  FileText,
  CheckCircle2,
  RefreshCw,
  Sliders,
  KeyRound,
  GitFork,
  Share2,
  Terminal,
  Code2,
  Copy,
  Check,
  Wrench,
  FolderGit2,
  AlertTriangle,
  ArrowLeft,
  Search,
  ExternalLink
} from 'lucide-react';

export default function DocumentationPage() {
  const navigate = useNavigate();
  const [activeSection, setActiveSection] = useState('overview');
  const [searchQuery, setSearchQuery] = useState('');
  const [copiedCode, setCopiedCode] = useState(null);

  const copyToClipboard = (text, id) => {
    navigator.clipboard.writeText(text);
    setCopiedCode(id);
    setTimeout(() => setCopiedCode(null), 2000);
  };

  const sections = [
    { id: 'overview', title: '01. Overview & Vision', icon: BookOpen },
    { id: 'security-triad', title: '02. Security & Immutability', icon: ShieldCheck },
    { id: 'architecture', title: '03. Architecture & Data Flow', icon: Layers },
    { id: 'm0-m1-chain', title: '04. M0/M1 Verification Chain', icon: GitCommit },
    { id: 'resilience', title: '05. Resilience & BYOK', icon: RefreshCw },
    { id: 'compliance', title: '06. Regulatory Compliance', icon: Scale },
    { id: 'forensics', title: '07. AI Forensic Analysis', icon: SearchCheck },
    { id: 'remix-dag', title: '08. Remix Lineage DAG', icon: GitFork },
    { id: 'api-reference', title: '09. Interactive API Surface', icon: Terminal },
    { id: 'setup-guide', title: '10. Setup & Environment', icon: Wrench },
    { id: 'non-claims', title: '11. Boundaries & Non-Claims', icon: AlertTriangle },
  ];

  useEffect(() => {
    const handleScroll = () => {
      const scrollPosition = window.scrollY + 140;
      for (const section of sections) {
        const element = document.getElementById(section.id);
        if (element) {
          const top = element.offsetTop;
          const height = element.offsetHeight;
          if (scrollPosition >= top && scrollPosition < top + height) {
            setActiveSection(section.id);
            break;
          }
        }
      }
    };
    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  const scrollToSection = (id) => {
    setActiveSection(id);
    const element = document.getElementById(id);
    if (element) {
      const yOffset = -100;
      const y = element.getBoundingClientRect().top + window.pageYOffset + yOffset;
      window.scrollTo({ top: y, behavior: 'smooth' });
    }
  };

  const filterMatch = (text) => {
    if (!searchQuery) return true;
    return text.toLowerCase().includes(searchQuery.toLowerCase());
  };

  return (
    <div className="bg-void-black text-on-surface font-body-base antialiased min-h-screen selection:bg-accent-blue/30 selection:text-white">
      {/* Sticky Docs Header */}
      <header className="sticky top-0 z-50 bg-void-black/90 backdrop-blur-md border-b border-frost-border py-4">
        <div className="max-w-[1400px] mx-auto px-6 flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <Link to="/" className="flex items-center gap-2 group">
              <Shield className="w-6 h-6 text-primary group-hover:text-accent-blue transition-colors" />
              <span className="font-section-heading text-xl font-bold tracking-tighter text-primary">Notary</span>
            </Link>
            <span className="text-frost-border">/</span>
            <span className="font-section-heading text-sm text-on-surface-variant uppercase tracking-widest font-semibold flex items-center gap-2">
              <BookOpen className="w-4 h-4 text-accent-blue" />
              Documentation
            </span>
          </div>

          {/* Search Bar */}
          <div className="relative w-full md:w-96">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-on-surface-variant" />
            <input
              type="text"
              placeholder="Search docs, APIs, compliance..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full bg-surface-container-low border border-frost-border rounded-full pl-9 pr-4 py-2 text-xs font-body-base text-on-surface placeholder:text-on-surface-variant focus:outline-none focus:border-accent-blue transition-colors"
            />
          </div>

          <div className="flex items-center gap-4">
            <button
              onClick={() => navigate('/app')}
              className="flex items-center gap-2 bg-primary text-void-black px-5 py-2 rounded-full font-nav-link text-xs font-semibold hover:bg-near-white hover:scale-105 transition-all duration-300 shadow-lg shadow-primary/10"
            >
              <ArrowLeft className="w-3.5 h-3.5" />
              <span>Back to App</span>
            </button>
            <a
              href="https://github.com/Ksalgotra1/Notary"
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1.5 border border-frost-border bg-surface/50 text-on-surface-variant hover:text-primary px-4 py-2 rounded-full font-nav-link text-xs transition-colors"
            >
              <span>GitHub</span>
              <ExternalLink className="w-3 h-3" />
            </a>
          </div>
        </div>
      </header>

      {/* Main Content Layout */}
      <div className="max-w-[1400px] mx-auto px-6 py-10 flex gap-10 relative">
        {/* Left Sticky Table of Contents Sidebar */}
        <aside className="hidden lg:block w-72 shrink-0">
          <div className="sticky top-28 space-y-6">
            <div className="text-xs font-code-block uppercase tracking-widest text-on-surface-variant font-semibold">
              Table of Contents
            </div>
            <nav className="space-y-1">
              {sections.map((sec) => {
                const IconComponent = sec.icon;
                const active = activeSection === sec.id;
                return (
                  <button
                    key={sec.id}
                    onClick={() => scrollToSection(sec.id)}
                    className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-xs font-nav-link text-left transition-all duration-200 ${
                      active
                        ? 'bg-surface-container-high text-primary font-semibold border-l-2 border-accent-blue shadow-sm'
                        : 'text-on-surface-variant hover:text-primary hover:bg-white/[0.03]'
                    }`}
                  >
                    <IconComponent className={`w-4 h-4 shrink-0 ${active ? 'text-accent-blue' : 'text-on-surface-variant'}`} />
                    <span className="truncate">{sec.title}</span>
                  </button>
                );
              })}
            </nav>

            <div className="pt-6 border-t border-frost-border/40">
              <div className="p-4 rounded-xl border border-frost-border bg-surface-container-lowest text-xs space-y-2">
                <div className="flex items-center gap-2 text-accent-green font-code-block font-semibold">
                  <ShieldCheck className="w-4 h-4" />
                  <span>COMPLIANCE Active</span>
                </div>
                <p className="text-on-surface-variant text-[11px] leading-relaxed">
                  All manifests anchored in Backblaze B2 under strict WORM Object Lock mode.
                </p>
              </div>
            </div>
          </div>
        </aside>

        {/* Right Main Article Content */}
        <main className="flex-1 min-w-0 space-y-20 pb-24">
          {/* Title Banner */}
          <div className="border-b border-frost-border pb-10">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-accent-blue/10 border border-accent-blue/30 text-accent-blue font-code-block text-xs uppercase tracking-wider mb-4">
              <Award className="w-3.5 h-3.5" />
              <span>Technical Specification & Architecture Reference</span>
            </div>
            <h1 className="font-hero-display text-4xl sm:text-6xl text-primary mb-4 leading-tight">
              Notary Documentation
            </h1>
            <p className="font-sub-heading text-lg sm:text-xl text-on-surface-variant leading-relaxed max-w-3xl">
              A birth certificate for every AI-generated asset — notarized in Backblaze B2, signed with C2PA and Ed25519, and verifiable by anyone in seconds.
            </p>
          </div>

          {/* Section 01: Overview */}
          {filterMatch('overview') && (
            <section id="overview" className="scroll-mt-28 space-y-6">
              <div className="flex items-center gap-3">
                <BookOpen className="w-6 h-6 text-accent-blue" />
                <h2 className="font-section-heading text-2xl sm:text-3xl text-primary font-bold">
                  01. Overview & Vision
                </h2>
              </div>

              <div className="space-y-4 text-on-surface-variant text-sm sm:text-base leading-relaxed">
                <p>
                  Every image or video generated by Notary receives a notarized record detailing exact generation metadata — provider, model, prompt, parameters, and timestamp — locked as a canonical <strong className="text-primary">Genblaze manifest</strong> in <strong className="text-primary">Backblaze B2</strong>.
                </p>
                <p>
                  With <strong className="text-accent-green">B2 COMPLIANCE Object Lock</strong> enabled, records cannot be modified or deleted by anyone — not even by Notary itself.
                </p>
              </div>

              {/* Stack Badges */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 pt-2">
                <div className="p-4 border border-frost-border rounded-xl bg-surface/30 flex flex-col gap-1">
                  <span className="text-xs text-on-surface-variant font-code-block">Storage Layer</span>
                  <span className="text-sm text-primary font-section-heading font-semibold flex items-center gap-1.5">
                    <Database className="w-4 h-4 text-accent-orange" />
                    Backblaze B2 WORM
                  </span>
                </div>
                <div className="p-4 border border-frost-border rounded-xl bg-surface/30 flex flex-col gap-1">
                  <span className="text-xs text-on-surface-variant font-code-block">Pipeline Engine</span>
                  <span className="text-sm text-primary font-section-heading font-semibold flex items-center gap-1.5">
                    <Cpu className="w-4 h-4 text-accent-blue" />
                    Genblaze Pipeline
                  </span>
                </div>
                <div className="p-4 border border-frost-border rounded-xl bg-surface/30 flex flex-col gap-1">
                  <span className="text-xs text-on-surface-variant font-code-block">Provenance Standard</span>
                  <span className="text-sm text-primary font-section-heading font-semibold flex items-center gap-1.5">
                    <FileCheck className="w-4 h-4 text-accent-green" />
                    C2PA JUMBF + ES256
                  </span>
                </div>
                <div className="p-4 border border-frost-border rounded-xl bg-surface/30 flex flex-col gap-1">
                  <span className="text-xs text-on-surface-variant font-code-block">Cryptographic Trust</span>
                  <span className="text-sm text-primary font-section-heading font-semibold flex items-center gap-1.5">
                    <Key className="w-4 h-4 text-accent-yellow" />
                    Ed25519 Signatures
                  </span>
                </div>
              </div>
            </section>
          )}

          {/* Section 02: Security & Immutability Triad */}
          {filterMatch('security') && (
            <section id="security-triad" className="scroll-mt-28 space-y-6 pt-8 border-t border-frost-border">
              <div className="flex items-center gap-3">
                <ShieldCheck className="w-6 h-6 text-accent-green" />
                <h2 className="font-section-heading text-2xl sm:text-3xl text-primary font-bold">
                  02. Core Security & Immutability Triad
                </h2>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="p-6 border border-frost-border rounded-2xl bg-surface/20 space-y-3">
                  <div className="flex items-center gap-3 text-accent-green">
                    <FileCheck className="w-5 h-5" />
                    <h3 className="font-sub-heading text-lg text-primary font-semibold">C2PA Content Credentials</h3>
                  </div>
                  <p className="text-xs text-on-surface-variant leading-relaxed">
                    Injects standard C2PA JUMBF metadata headers using <code className="text-accent-blue font-code-block">c2pa-python</code> and local X.509 ES256 cert chains (<code className="text-accent-blue font-code-block">es256_certs.pem</code> + <code className="text-accent-blue font-code-block">c2pa_root_ca.pem</code>). Satisfies EU AI Act Article 50 (EU-ART50-02) machine-readable marking requirement.
                  </p>
                </div>

                <div className="p-6 border border-frost-border rounded-2xl bg-surface/20 space-y-3">
                  <div className="flex items-center gap-3 text-accent-yellow">
                    <Key className="w-5 h-5" />
                    <h3 className="font-sub-heading text-lg text-primary font-semibold">Ed25519 Manifest Signatures</h3>
                  </div>
                  <p className="text-xs text-on-surface-variant leading-relaxed">
                    Provides an independent cryptographic trust anchor separate from B2. Every manifest is signed with an Ed25519 keypair. Public keys are served open via <code className="text-accent-blue font-code-block">GET /.well-known/notary-public-key.pem</code> for offline third-party verification.
                  </p>
                </div>

                <div className="p-6 border border-frost-border rounded-2xl bg-surface/20 space-y-3">
                  <div className="flex items-center gap-3 text-accent-blue">
                    <FileText className="w-5 h-5" />
                    <h3 className="font-sub-heading text-lg text-primary font-semibold">Steganographic Watermarking</h3>
                  </div>
                  <p className="text-xs text-on-surface-variant leading-relaxed">
                    Visual badge watermarking overlay applied via Pillow (<code className="text-accent-blue font-code-block">watermark.py</code>) prior to M0 manifest embedding. Ensures compliance with India IT Rules 2026 requirement (IN-SGI-02).
                  </p>
                </div>

                <div className="p-6 border border-frost-border rounded-2xl bg-surface/20 space-y-3">
                  <div className="flex items-center gap-3 text-accent-orange">
                    <Lock className="w-5 h-5" />
                    <h3 className="font-sub-heading text-lg text-primary font-semibold">B2 COMPLIANCE Object Lock</h3>
                  </div>
                  <p className="text-xs text-on-surface-variant leading-relaxed">
                    Storage bucket objects are written in COMPLIANCE lock mode (WORM - Write Once Read Many). Manifests cannot be deleted, altered, or overwritten by any user or API token during retention.
                  </p>
                </div>
              </div>
            </section>
          )}

          {/* Section 03: Architecture */}
          {filterMatch('architecture') && (
            <section id="architecture" className="scroll-mt-28 space-y-6 pt-8 border-t border-frost-border">
              <div className="flex items-center gap-3">
                <Layers className="w-6 h-6 text-accent-blue" />
                <h2 className="font-section-heading text-2xl sm:text-3xl text-primary font-bold">
                  03. Architecture & Data Flow
                </h2>
              </div>

              <p className="text-sm text-on-surface-variant leading-relaxed">
                Six layers, one direction of truth — the client never writes to Backblaze B2 directly.
              </p>

              {/* Architecture Spec Card */}
              <div className="p-6 border border-frost-border rounded-2xl bg-surface/30 space-y-4 font-code-block text-xs">
                <div className="text-accent-blue font-semibold uppercase tracking-wider">Pipeline Flow Overview</div>
                <div className="text-on-surface-variant space-y-2 leading-relaxed">
                  <div><span className="text-accent-green">[Client Layer]</span> React (Vite) → Generate UI / Public Verify Portal</div>
                  <div><span className="text-accent-yellow">[API Layer]</span> FastAPI (<code className="text-primary">routes.py</code>) → Handles policy checks, compliance, forensics</div>
                  <div><span className="text-accent-orange">[Logic Engine]</span> <code className="text-primary">compliance.py</code>, <code className="text-primary">signing.py</code>, <code className="text-primary">c2pa_signer.py</code>, <code className="text-primary">watermark.py</code></div>
                  <div><span className="text-accent-blue">[Pipeline Layer]</span> Genblaze Pipeline → Executes provider step & writes receipt</div>
                  <div><span className="text-primary">[Storage Layer]</span> Backblaze B2 Bucket (Object Lock WORM) → Manifests & Assets</div>
                </div>
              </div>
            </section>
          )}

          {/* Section 04: M0/M1 Chain */}
          {filterMatch('m0') && (
            <section id="m0-m1-chain" className="scroll-mt-28 space-y-6 pt-8 border-t border-frost-border">
              <div className="flex items-center gap-3">
                <GitCommit className="w-6 h-6 text-accent-yellow" />
                <h2 className="font-section-heading text-2xl sm:text-3xl text-primary font-bold">
                  04. How Verification Works — The M0 / M1 Chain
                </h2>
              </div>

              <div className="space-y-4 text-sm text-on-surface-variant leading-relaxed">
                <p>
                  An embedded manifest cannot carry the hash of the file that contains it — embedding changes the file's bytes, altering the hash. Notary solves this with a two-record chain:
                </p>
                
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2">
                  <div className="p-5 border border-frost-border rounded-xl bg-surface/20 space-y-2">
                    <span className="text-xs font-code-block text-accent-blue font-semibold">Record M0 (Raw Manifest)</span>
                    <p className="text-xs text-on-surface-variant">
                      Raw provider-generation manifest, embedded into image bytes unchanged alongside C2PA headers and visual watermark.
                    </p>
                  </div>
                  <div className="p-5 border border-frost-border rounded-xl bg-surface/20 space-y-2">
                    <span className="text-xs font-code-block text-accent-green font-semibold">Record M1 (Final Receipt / run_id)</span>
                    <p className="text-xs text-on-surface-variant">
                      Locked receipt whose parent is M0. Hash covers final post-embed bytes. Public <code className="text-primary">run_id</code> refers to M1.
                    </p>
                  </div>
                </div>
              </div>
            </section>
          )}

          {/* Section 05: Provider Resilience & BYOK */}
          {filterMatch('resilience') && (
            <section id="resilience" className="scroll-mt-28 space-y-6 pt-8 border-t border-frost-border">
              <div className="flex items-center gap-3">
                <RefreshCw className="w-6 h-6 text-accent-orange" />
                <h2 className="font-section-heading text-2xl sm:text-3xl text-primary font-bold">
                  05. Provider Resilience & Bring Your Own Keys (BYOK)
                </h2>
              </div>

              <div className="space-y-4 text-sm text-on-surface-variant leading-relaxed">
                <p>
                  Notary implements an automated fallback cascade so requests succeed even when quota limits are reached:
                </p>
                <div className="p-4 border border-frost-border rounded-xl bg-surface/30 font-code-block text-xs text-on-surface-variant space-y-1">
                  <div>1. <strong className="text-primary">Google Gemini 2.5 Flash Image</strong> (Multi-key pool rotation)</div>
                  <div>2. <strong className="text-accent-yellow">NVIDIA NIM</strong> (FLUX.1 Schnell)</div>
                  <div>3. <strong className="text-accent-blue">Hugging Face Space</strong> (FLUX.2-klein-4B)</div>
                  <div>4. <strong className="text-accent-green">Pollinations FLUX</strong> (Optional fallback)</div>
                </div>

                <div className="p-5 border border-frost-border rounded-xl bg-surface/20 space-y-2">
                  <div className="flex items-center gap-2 text-primary font-sub-heading text-base font-semibold">
                    <KeyRound className="w-4 h-4 text-accent-yellow" />
                    <span>BYOK Privacy Rules</span>
                  </div>
                  <p className="text-xs text-on-surface-variant">
                    Keys entered in the UI are held in browser tab session storage only, sent to backend per-request, and never stored to B2, database, or manifests.
                  </p>
                </div>
              </div>
            </section>
          )}

          {/* Section 06: Regulatory Compliance */}
          {filterMatch('compliance') && (
            <section id="compliance" className="scroll-mt-28 space-y-6 pt-8 border-t border-frost-border">
              <div className="flex items-center gap-3">
                <Scale className="w-6 h-6 text-accent-green" />
                <h2 className="font-section-heading text-2xl sm:text-3xl text-primary font-bold">
                  06. Regulatory Compliance Engine (9/9 Checks)
                </h2>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="p-6 border border-frost-border rounded-2xl bg-surface/20 space-y-3">
                  <h3 className="font-sub-heading text-lg text-primary font-semibold">India IT Rules 2026</h3>
                  <ul className="text-xs text-on-surface-variant space-y-2 list-disc list-inside">
                    <li>User declaration & provenance logging</li>
                    <li>Visible label overlay (<code className="text-accent-blue">watermark.py</code>)</li>
                    <li>Audio disclosure prefix check</li>
                    <li>Embedded permanent metadata (M0)</li>
                    <li>Unique identifier & traceability</li>
                  </ul>
                </div>

                <div className="p-6 border border-frost-border rounded-2xl bg-surface/20 space-y-3">
                  <h3 className="font-sub-heading text-lg text-primary font-semibold">EU AI Act Article 50</h3>
                  <ul className="text-xs text-on-surface-variant space-y-2 list-disc list-inside">
                    <li>Provider identification</li>
                    <li>Machine-readable C2PA JUMBF mark (<code className="text-accent-blue">c2pa_signer.py</code>)</li>
                    <li>AI-generated disclosure notice</li>
                    <li>Provenance traceability chain</li>
                  </ul>
                </div>
              </div>
            </section>
          )}

          {/* Section 07: AI Forensic Analysis */}
          {filterMatch('forensic') && (
            <section id="forensics" className="scroll-mt-28 space-y-6 pt-8 border-t border-frost-border">
              <div className="flex items-center gap-3">
                <SearchCheck className="w-6 h-6 text-accent-blue" />
                <h2 className="font-section-heading text-2xl sm:text-3xl text-primary font-bold">
                  07. AI Forensic Verification
                </h2>
              </div>

              <p className="text-sm text-on-surface-variant leading-relaxed">
                When a file fails verification hash check, Gemini Vision compares the submitted file against B2 canonical asset and explains <strong className="text-primary">what</strong> was altered:
              </p>

              <div className="p-5 border border-frost-border rounded-xl bg-void-black font-code-block text-xs space-y-1 overflow-x-auto">
                <div className="text-on-surface-variant font-semibold">// Example Gemini Vision forensic response:</div>
                <div className="text-accent-green">{'{'}</div>
                <div className="text-on-surface-variant pl-4">"modifications_detected": ["Text overlay added in lower third", "Color grading shifted warmer"],</div>
                <div className="text-on-surface-variant pl-4">"severity": "moderate",</div>
                <div className="text-on-surface-variant pl-4">"conclusion": "Submitted file is a derivative modification of canonical B2 asset."</div>
                <div className="text-accent-green">{'}'}</div>
              </div>
            </section>
          )}

          {/* Section 08: Remix DAG */}
          {filterMatch('remix') && (
            <section id="remix-dag" className="scroll-mt-28 space-y-6 pt-8 border-t border-frost-border">
              <div className="flex items-center gap-3">
                <GitFork className="w-6 h-6 text-accent-yellow" />
                <h2 className="font-section-heading text-2xl sm:text-3xl text-primary font-bold">
                  08. Remix Lineage DAG
                </h2>
              </div>

              <p className="text-sm text-on-surface-variant leading-relaxed">
                Regenerating from an asset links the new run via Genblaze's <code className="text-accent-blue font-code-block">from_result()</code>. Full ancestry is rendered as a navigable Directed Acyclic Graph (DAG):
              </p>

              <div className="p-6 border border-frost-border rounded-2xl bg-surface/20 flex flex-wrap gap-4 items-center justify-center font-code-block text-xs">
                <div className="px-4 py-2 rounded-lg border border-frost-border bg-void-black text-accent-blue">v1 (Original)</div>
                <span className="text-on-surface-variant">→</span>
                <div className="px-4 py-2 rounded-lg border border-frost-border bg-void-black text-accent-yellow">v2 (Remix: Warmer Lighting)</div>
                <span className="text-on-surface-variant">→</span>
                <div className="px-4 py-2 rounded-lg border border-accent-green bg-accent-green/10 text-accent-green">v3 (Current Asset)</div>
              </div>
            </section>
          )}

          {/* Section 09: API Reference */}
          {filterMatch('api') && (
            <section id="api-reference" className="scroll-mt-28 space-y-6 pt-8 border-t border-frost-border">
              <div className="flex items-center gap-3">
                <Terminal className="w-6 h-6 text-accent-green" />
                <h2 className="font-section-heading text-2xl sm:text-3xl text-primary font-bold">
                  09. Interactive API Surface Reference
                </h2>
              </div>

              <div className="space-y-4">
                {[
                  { method: 'POST', path: '/generate', desc: 'Trigger asset generation pipeline', code: 'curl -X POST "http://localhost:8000/generate" -H "Content-Type: application/json" -d \'{"prompt": "A futuristic city in rain", "modality": "image"}\'' },
                  { method: 'GET', path: '/assets/{run_id}', desc: 'Fetch full manifest & asset URL', code: 'curl "http://localhost:8000/assets/RUN_ID"' },
                  { method: 'POST', path: '/assets/{run_id}/verify', desc: 'Verify byte hash against M1 receipt', code: 'curl -X POST "http://localhost:8000/assets/RUN_ID/verify" -H "Content-Type: application/json" -d \'{"file_hash": "a1b2c3..."}\'' },
                  { method: 'GET', path: '/.well-known/notary-public-key.pem', desc: 'Fetch Ed25519 public key for offline manifest signature check', code: 'curl "http://localhost:8000/.well-known/notary-public-key.pem"' },
                  { method: 'GET', path: '/public/verify/{run_id}', desc: 'Public portal verify payload (no auth required)', code: 'curl "http://localhost:8000/public/verify/RUN_ID"' },
                ].map((ep, idx) => (
                  <div key={idx} className="p-5 border border-frost-border rounded-xl bg-surface/20 space-y-3">
                    <div className="flex items-center justify-between gap-4 flex-wrap">
                      <div className="flex items-center gap-3">
                        <span className={`px-2.5 py-1 rounded font-code-block text-xs font-bold ${ep.method === 'POST' ? 'bg-accent-blue/20 text-accent-blue' : 'bg-accent-green/20 text-accent-green'}`}>
                          {ep.method}
                        </span>
                        <code className="text-primary font-code-block text-sm font-semibold">{ep.path}</code>
                      </div>
                      <span className="text-xs text-on-surface-variant">{ep.desc}</span>
                    </div>

                    <div className="relative group">
                      <pre className="p-3 rounded-lg bg-void-black border border-frost-border/60 text-[11px] font-code-block text-on-surface-variant overflow-x-auto">
                        {ep.code}
                      </pre>
                      <button
                        onClick={() => copyToClipboard(ep.code, `ep-${idx}`)}
                        className="absolute right-2 top-2 p-1.5 rounded bg-surface/80 hover:bg-surface text-on-surface-variant hover:text-primary transition-colors"
                        title="Copy command"
                      >
                        {copiedCode === `ep-${idx}` ? <Check className="w-3.5 h-3.5 text-accent-green" /> : <Copy className="w-3.5 h-3.5" />}
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </section>
          )}

          {/* Section 10: Setup Guide */}
          {filterMatch('setup') && (
            <section id="setup-guide" className="scroll-mt-28 space-y-6 pt-8 border-t border-frost-border">
              <div className="flex items-center gap-3">
                <Wrench className="w-6 h-6 text-accent-blue" />
                <h2 className="font-section-heading text-2xl sm:text-3xl text-primary font-bold">
                  10. Setup & Local Development
                </h2>
              </div>

              <div className="space-y-4">
                <div className="p-5 border border-frost-border rounded-xl bg-surface/20 space-y-3">
                  <span className="text-xs font-code-block text-primary font-semibold">Backend Setup</span>
                  <pre className="p-3 rounded-lg bg-void-black border border-frost-border text-xs font-code-block text-on-surface-variant">
                    cd backend{'\n'}python -m venv .venv{'\n'}source .venv/bin/activate{'\n'}pip install -r requirements.txt{'\n'}uvicorn main:app --reload --port 8000
                  </pre>
                </div>

                <div className="p-5 border border-frost-border rounded-xl bg-surface/20 space-y-3">
                  <span className="text-xs font-code-block text-primary font-semibold">Frontend Setup</span>
                  <pre className="p-3 rounded-lg bg-void-black border border-frost-border text-xs font-code-block text-on-surface-variant">
                    cd frontend{'\n'}npm install{'\n'}npm run dev
                  </pre>
                </div>
              </div>
            </section>
          )}

          {/* Section 11: Boundaries */}
          {filterMatch('non-claims') && (
            <section id="non-claims" className="scroll-mt-28 space-y-6 pt-8 border-t border-frost-border">
              <div className="flex items-center gap-3">
                <AlertTriangle className="w-6 h-6 text-accent-yellow" />
                <h2 className="font-section-heading text-2xl sm:text-3xl text-primary font-bold">
                  11. Boundaries & Non-Claims
                </h2>
              </div>

              <div className="p-6 border border-accent-yellow/30 rounded-2xl bg-accent-yellow/5 space-y-3 text-xs sm:text-sm text-on-surface-variant leading-relaxed">
                <p>
                  Notary embeds Genblaze manifests and locks them with Backblaze B2 COMPLIANCE Object Lock.
                </p>
                <p>
                  Compliance scorecards report what a manifest can observe automatically — they are analytical tools, not formal legal advice. Policy review is explainable rule-matching, not an absolute guarantee.
                </p>
              </div>
            </section>
          )}
        </main>
      </div>
    </div>
  );
}
