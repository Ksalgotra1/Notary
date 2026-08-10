import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Shield, Sparkles, Lock, CheckCircle2, ArrowRight, Scale, FileCheck, Key, SearchCheck, ShieldCheck } from 'lucide-react';
import HeroAnimation from '../components/HeroAnimation';

export default function LandingPage() {
  const navigate = useNavigate();
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const handleScroll = () => {
      setScrolled(window.scrollY > 40);
    };
    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  return (
    <div className="bg-void-black text-on-surface font-body-base antialiased min-h-screen overflow-x-hidden selection:bg-accent-blue/30 selection:text-white">
      {/* Sticky Header / Navbar */}
      <header className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 ${scrolled ? 'bg-void-black/80 backdrop-blur-md border-b border-frost-border py-4' : 'bg-transparent py-6'}`}>
        <div className="max-w-container-max mx-auto px-md flex items-center justify-between">
          <Link to="/" className="flex items-center gap-3 group">
            <Shield className="w-6 h-6 text-primary group-hover:text-accent-blue transition-colors" />
            <span className="font-section-heading text-xl font-bold tracking-tighter text-primary">Notary</span>
          </Link>
          
          <nav className="hidden md:flex items-center gap-8 font-nav-link text-nav-link">
            <Link to="/app" className="text-on-surface-variant hover:text-primary transition-colors">App</Link>
            <Link to="/docs" className="text-on-surface-variant hover:text-primary transition-colors">Docs</Link>
            <Link to="/app/library" className="text-on-surface-variant hover:text-primary transition-colors">Library</Link>
            <Link to="/app/dashboard" className="text-on-surface-variant hover:text-primary transition-colors">Dashboard</Link>
            <a href="https://github.com/Ksalgotra1/Notary" target="_blank" rel="noopener noreferrer" className="text-on-surface-variant hover:text-primary transition-colors">GitHub</a>
          </nav>

          <div className="flex items-center gap-4">
            <button 
              onClick={() => navigate('/app')}
              className="bg-primary text-void-black px-6 py-2.5 rounded-full font-nav-link text-sm hover:bg-near-white hover:scale-105 transition-all duration-300 shadow-lg shadow-primary/10 flex items-center gap-2"
            >
              <span>Get Started</span>
              <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      </header>

      <main>
        {/* Hero Section */}
        <section className="min-h-screen flex items-center justify-center px-md relative overflow-hidden pt-20">
          {/* 3D Animation Background */}
          <div className="absolute inset-0 z-0">
            <HeroAnimation />
            {/* Gradient fade to black at bottom */}
            <div className="absolute bottom-0 left-0 w-full h-1/2 bg-gradient-to-t from-void-black via-void-black/80 to-transparent z-10 pointer-events-none" />
            <div className="absolute inset-0 bg-void-black/40 z-10 pointer-events-none" />
          </div>

          {/* Center Content */}
          <div className="max-w-4xl mx-auto z-20 relative text-center flex flex-col items-center">
            <h1 className="font-hero-display text-5xl sm:text-7xl md:text-8xl text-primary drop-shadow-2xl leading-none mb-6 tracking-tight">
              Immutable<br />Provenance<br />for the AI Era
            </h1>
            <p className="font-sub-heading text-lg sm:text-xl text-on-surface-variant max-w-2xl mx-auto drop-shadow-lg mb-10 leading-relaxed">
              Establish trust in an age of synthetic media. Securely generate, permanently anchor, and universally verify the origins of your digital assets.
            </p>
            <div className="flex flex-col sm:flex-row items-center justify-center gap-4 w-full sm:w-auto">
              <button 
                onClick={() => navigate('/app')}
                className="w-full sm:w-auto bg-primary text-void-black px-8 py-4 rounded-full font-nav-link text-base hover:scale-105 transition-transform duration-300 shadow-xl shadow-primary/20"
              >
                Get Started
              </button>
              <button 
                onClick={() => navigate('/docs')}
                className="w-full sm:w-auto bg-void-black/50 backdrop-blur-md border border-frost-border text-on-surface px-8 py-4 rounded-full font-nav-link text-base hover:bg-white/10 transition-all duration-300"
              >
                View Documentation
              </button>
            </div>
          </div>
        </section>

        {/* Value Proposition (The Lifecycle) */}
        <section className="py-hero-gap px-md max-w-container-max mx-auto relative z-20">
          {/* Symmetrical Section Divider Line */}
          <div className="w-full border-t border-frost-border mb-16" />

          <div className="text-center mb-16">
            <h2 className="font-hero-display text-4xl sm:text-6xl md:text-7xl text-primary mb-4 leading-none">
              The Provenance Lifecycle
            </h2>
            <p className="font-sub-heading text-on-surface-variant text-base sm:text-lg max-w-2xl mx-auto">
              An end-to-end cryptographic pipeline designed for absolute media integrity.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            {/* 01 Generate */}
            <div 
              className="bg-surface/20 border border-frost-border rounded-2xl p-8 flex flex-col gap-6 hover:bg-surface/40 hover:border-accent-blue/40 hover:-translate-y-2 hover:scale-[1.01] hover:shadow-[0_12px_35px_rgba(59,158,255,0.12)] transition-all duration-500 relative group overflow-hidden"
              style={{ boxShadow: 'rgba(176, 199, 217, 0.145) 0px 0px 0px 1px inset' }}
            >
              <div className="absolute top-0 right-0 w-36 h-36 bg-accent-blue/15 blur-3xl rounded-full -mr-16 -mt-16 transition-opacity opacity-0 group-hover:opacity-100 duration-500" />
              <div className="flex items-center justify-between">
                <span className="text-on-surface-variant font-code-block text-sm group-hover:text-accent-blue transition-colors">01</span>
                <Sparkles className="text-on-surface-variant group-hover:text-accent-blue group-hover:rotate-12 w-6 h-6 transition-all duration-300" />
              </div>
              <div>
                <h3 className="font-sub-heading text-2xl text-primary mb-3 group-hover:text-white transition-colors">Generate</h3>
                <p className="text-on-surface-variant text-sm leading-relaxed">
                  Create assets within our secure enclave. Every generation event is cryptographically signed at the exact moment of creation.
                </p>
              </div>
              {/* Code Preview Visual */}
              <div 
                className="mt-auto bg-void-black border border-frost-border rounded-2xl p-4 text-xs font-code-block text-on-surface-variant overflow-x-auto group-hover:border-accent-blue/30 transition-colors"
                style={{ boxShadow: 'rgba(176, 199, 217, 0.145) 0px 0px 0px 1px inset' }}
              >
                <span className="text-accent-blue">const</span> asset = <span className="text-accent-blue">await</span> notary.<span className="text-accent-yellow">generate</span>({'{'}<br />
                &nbsp;&nbsp;model: <span className="text-accent-green">'flux-v1'</span>,<br />
                &nbsp;&nbsp;prompt: <span className="text-accent-green">'hyper-realistic...'</span><br />
                {'}'});
              </div>
            </div>

            {/* 02 Anchor */}
            <div 
              className="bg-surface/20 border border-frost-border rounded-2xl p-8 flex flex-col gap-6 hover:bg-surface/40 hover:border-accent-yellow/40 hover:-translate-y-2 hover:scale-[1.01] hover:shadow-[0_12px_35px_rgba(255,197,61,0.12)] transition-all duration-500 relative group overflow-hidden"
              style={{ boxShadow: 'rgba(176, 199, 217, 0.145) 0px 0px 0px 1px inset' }}
            >
              <div className="absolute top-0 right-0 w-36 h-36 bg-accent-yellow/20 blur-3xl rounded-full -mr-16 -mt-16 transition-opacity opacity-0 group-hover:opacity-100 duration-500" />
              <div className="flex items-center justify-between">
                <span className="text-on-surface-variant font-code-block text-sm group-hover:text-accent-yellow transition-colors">02</span>
                <Lock className="text-accent-yellow group-hover:scale-110 w-6 h-6 transition-transform duration-300" />
              </div>
              <div>
                <h3 className="font-sub-heading text-2xl text-primary mb-3 group-hover:text-white transition-colors">Anchor</h3>
                <p className="text-on-surface-variant text-sm leading-relaxed">
                  The cryptographic hash of your asset is anchored to a decentralized, immutable ledger, establishing irrefutable proof of time and origin.
                </p>
              </div>
              {/* Visual Indicator */}
              <div 
                className="mt-auto h-32 border border-frost-border rounded-2xl flex items-center justify-center bg-void-black relative overflow-hidden group-hover:border-accent-yellow/30 transition-colors"
                style={{ boxShadow: 'rgba(176, 199, 217, 0.145) 0px 0px 0px 1px inset' }}
              >
                <div className="w-16 h-16 rounded-full border border-accent-yellow/30 flex items-center justify-center relative z-10 group-hover:scale-110 transition-transform duration-500">
                  <div className="w-12 h-12 rounded-full border border-accent-yellow/50 flex items-center justify-center">
                    <div className="w-8 h-8 rounded-full bg-accent-yellow/20 flex items-center justify-center blur-[2px]" />
                  </div>
                </div>
                <div className="absolute w-full h-[1px] bg-gradient-to-r from-transparent via-accent-yellow/40 to-transparent" />
              </div>
            </div>

            {/* 03 Verify */}
            <div 
              className="bg-surface/20 border border-frost-border rounded-2xl p-8 flex flex-col gap-6 hover:bg-surface/40 hover:border-accent-green/40 hover:-translate-y-2 hover:scale-[1.01] hover:shadow-[0_12px_35px_rgba(17,255,153,0.12)] transition-all duration-500 relative group overflow-hidden"
              style={{ boxShadow: 'rgba(176, 199, 217, 0.145) 0px 0px 0px 1px inset' }}
            >
              <div className="absolute top-0 right-0 w-36 h-36 bg-accent-green/20 blur-3xl rounded-full -mr-16 -mt-16 transition-opacity opacity-0 group-hover:opacity-100 duration-500" />
              <div className="flex items-center justify-between">
                <span className="text-on-surface-variant font-code-block text-sm group-hover:text-accent-green transition-colors">03</span>
                <CheckCircle2 className="text-accent-green group-hover:scale-110 w-6 h-6 transition-transform duration-300" />
              </div>
              <div>
                <h3 className="font-sub-heading text-2xl text-primary mb-3 group-hover:text-white transition-colors">Verify</h3>
                <p className="text-on-surface-variant text-sm leading-relaxed">
                  Instantly verify the authenticity of any asset. Our open protocol ensures transparency without exposing sensitive raw data.
                </p>
              </div>
              {/* Visual Indicator */}
              <div 
                className="mt-auto h-32 border border-frost-border rounded-2xl flex items-center justify-center bg-void-black relative overflow-hidden group-hover:border-accent-green/30 transition-colors"
                style={{ boxShadow: 'rgba(176, 199, 217, 0.145) 0px 0px 0px 1px inset' }}
              >
                <div className="px-4 py-2 rounded-full bg-accent-green/10 border border-accent-green/30 flex items-center gap-2 group-hover:bg-accent-green/20 group-hover:border-accent-green/50 transition-all duration-300">
                  <CheckCircle2 className="text-accent-green w-4 h-4" />
                  <span className="text-accent-green font-code-block text-xs uppercase tracking-wider font-semibold">Provenance Valid</span>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Core Features */}
        <section className="py-20 px-md max-w-container-max mx-auto relative">
          {/* Symmetrical Section Divider Line */}
          <div className="w-full border-t border-frost-border mb-16" />

          <div className="mb-16 text-center flex flex-col items-center">
            <h2 className="font-hero-display text-4xl sm:text-6xl text-primary mb-4 leading-none">
              Core Features
            </h2>
            <p className="font-sub-heading text-on-surface-variant text-base sm:text-lg max-w-2xl mx-auto text-center">
              Engineered for tamper-evident provenance, regulatory compliance, and cryptographic verification.
            </p>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {/* Card 1: C2PA Credentials */}
            <div 
              className="p-8 border border-frost-border rounded-2xl bg-surface/10 hover:bg-surface/30 hover:border-accent-blue/40 hover:-translate-y-1.5 hover:shadow-[0_10px_30px_rgba(59,158,255,0.1)] transition-all duration-300 group flex flex-col justify-between"
              style={{ boxShadow: 'rgba(176, 199, 217, 0.145) 0px 0px 0px 1px inset' }}
            >
              <div>
                <div className="w-10 h-10 rounded-xl bg-accent-blue/10 border border-accent-blue/30 flex items-center justify-center mb-6 group-hover:scale-110 transition-transform duration-300">
                  <FileCheck className="w-5 h-5 text-accent-blue" />
                </div>
                <h3 className="font-sub-heading text-xl text-primary mb-2 group-hover:text-accent-blue transition-colors font-semibold">C2PA Content Credentials</h3>
                <p className="text-on-surface-variant text-sm leading-relaxed">
                  JUMBF metadata headers & X.509 certificate signing satisfying EU AI Act Article 50.
                </p>
              </div>
            </div>

            {/* Card 2: Ed25519 Manifest Signing */}
            <div 
              className="p-8 border border-frost-border rounded-2xl bg-surface/10 hover:bg-surface/30 hover:border-accent-yellow/40 hover:-translate-y-1.5 hover:shadow-[0_10px_30px_rgba(255,197,61,0.1)] transition-all duration-300 group flex flex-col justify-between"
              style={{ boxShadow: 'rgba(176, 199, 217, 0.145) 0px 0px 0px 1px inset' }}
            >
              <div>
                <div className="w-10 h-10 rounded-xl bg-accent-yellow/10 border border-accent-yellow/30 flex items-center justify-center mb-6 group-hover:scale-110 transition-transform duration-300">
                  <Key className="w-5 h-5 text-accent-yellow" />
                </div>
                <h3 className="font-sub-heading text-xl text-primary mb-2 group-hover:text-accent-yellow transition-colors font-semibold">Ed25519 Signatures</h3>
                <p className="text-on-surface-variant text-sm leading-relaxed">
                  Independent digital signatures with open public key verification at <code className="text-accent-yellow text-xs font-code-block">/.well-known</code>.
                </p>
              </div>
            </div>

            {/* Card 3: Regulatory Compliance Engine */}
            <div 
              className="p-8 border border-frost-border rounded-2xl bg-surface/10 hover:bg-surface/30 hover:border-accent-green/40 hover:-translate-y-1.5 hover:shadow-[0_10px_30px_rgba(17,255,153,0.1)] transition-all duration-300 group flex flex-col justify-between"
              style={{ boxShadow: 'rgba(176, 199, 217, 0.145) 0px 0px 0px 1px inset' }}
            >
              <div>
                <div className="w-10 h-10 rounded-xl bg-accent-green/10 border border-accent-green/30 flex items-center justify-center mb-6 group-hover:scale-110 transition-transform duration-300">
                  <Scale className="w-5 h-5 text-accent-green" />
                </div>
                <h3 className="font-sub-heading text-xl text-primary mb-2 group-hover:text-accent-green transition-colors font-semibold">Compliance Engine</h3>
                <p className="text-on-surface-variant text-sm leading-relaxed">
                  9/9 automated requirement checks against India IT Rules 2026 & EU AI Act standards.
                </p>
              </div>
            </div>

            {/* Card 4: AI Forensic Verification */}
            <div 
              className="p-8 border border-frost-border rounded-2xl bg-surface/10 hover:bg-surface/30 hover:border-accent-orange/40 hover:-translate-y-1.5 hover:shadow-[0_10px_30px_rgba(255,128,31,0.1)] transition-all duration-300 group flex flex-col justify-between"
              style={{ boxShadow: 'rgba(176, 199, 217, 0.145) 0px 0px 0px 1px inset' }}
            >
              <div>
                <div className="w-10 h-10 rounded-xl bg-accent-orange/10 border border-accent-orange/30 flex items-center justify-center mb-6 group-hover:scale-110 transition-transform duration-300">
                  <SearchCheck className="w-5 h-5 text-accent-orange" />
                </div>
                <h3 className="font-sub-heading text-xl text-primary mb-2 group-hover:text-accent-orange transition-colors font-semibold">AI Forensic Analysis</h3>
                <p className="text-on-surface-variant text-sm leading-relaxed">
                  Gemini Vision analysis identifies text overlays, crops, and color shifts on hash mismatches.
                </p>
              </div>
            </div>

            {/* Card 5: Steganographic Watermarking */}
            <div 
              className="p-8 border border-frost-border rounded-2xl bg-surface/10 hover:bg-surface/30 hover:border-accent-blue/40 hover:-translate-y-1.5 hover:shadow-[0_10px_30px_rgba(59,158,255,0.1)] transition-all duration-300 group flex flex-col justify-between"
              style={{ boxShadow: 'rgba(176, 199, 217, 0.145) 0px 0px 0px 1px inset' }}
            >
              <div>
                <div className="w-10 h-10 rounded-xl bg-accent-blue/10 border border-accent-blue/30 flex items-center justify-center mb-6 group-hover:scale-110 transition-transform duration-300">
                  <ShieldCheck className="w-5 h-5 text-accent-blue" />
                </div>
                <h3 className="font-sub-heading text-xl text-primary mb-2 group-hover:text-accent-blue transition-colors font-semibold">Visual Watermarking</h3>
                <p className="text-on-surface-variant text-sm leading-relaxed">
                  Pillow visual badge overlay fulfilling India IT Rules (IN-SGI-02) disclosure requirements.
                </p>
              </div>
            </div>

            {/* Card 6: B2 COMPLIANCE Object Lock */}
            <div 
              className="p-8 border border-frost-border rounded-2xl bg-surface/10 hover:bg-surface/30 hover:border-accent-green/40 hover:-translate-y-1.5 hover:shadow-[0_10px_30px_rgba(17,255,153,0.1)] transition-all duration-300 group flex flex-col justify-between"
              style={{ boxShadow: 'rgba(176, 199, 217, 0.145) 0px 0px 0px 1px inset' }}
            >
              <div>
                <div className="w-10 h-10 rounded-xl bg-accent-green/10 border border-accent-green/30 flex items-center justify-center mb-6 group-hover:scale-110 transition-transform duration-300">
                  <Lock className="w-5 h-5 text-accent-green" />
                </div>
                <h3 className="font-sub-heading text-xl text-primary mb-2 group-hover:text-accent-green transition-colors font-semibold">B2 COMPLIANCE Lock</h3>
                <p className="text-on-surface-variant text-sm leading-relaxed">
                  Immutable WORM storage layer anchored in Backblaze B2, un-deletable even by root.
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* Supported Enclaves */}
        <section className="py-hero-gap px-md max-w-container-max mx-auto relative overflow-hidden">
          {/* Symmetrical Section Divider Line */}
          <div className="w-full border-t border-frost-border mb-20" />
          <div className="grid grid-cols-1 md:grid-cols-12 gap-12 items-center">
            <div className="md:col-span-5 md:border-r border-frost-border md:pr-12">
              <h2 className="font-hero-display text-4xl sm:text-6xl text-primary leading-tight">
                Supported<br />Enclaves
              </h2>
            </div>
            <div className="md:col-span-7">
              <p className="font-sub-heading text-2xl sm:text-3xl md:text-4xl text-on-surface-variant leading-relaxed">
                We support{' '}
                <span className="font-section-heading font-bold text-primary tracking-widest uppercase inline-block border border-frost-border bg-surface/50 px-4 py-1.5 rounded-lg mx-1 my-1 shadow-[inset_0_0_10px_rgba(255,255,255,0.05)] hover:border-accent-blue hover:text-white hover:scale-105 hover:shadow-[0_0_20px_rgba(59,158,255,0.25)] transition-all duration-300">
                  GOOGLE
                </span>,{' '}
                <span className="font-section-heading font-bold text-primary tracking-widest uppercase inline-block border border-frost-border bg-surface/50 px-4 py-1.5 rounded-lg mx-1 my-1 shadow-[inset_0_0_10px_rgba(255,255,255,0.05)] hover:border-accent-yellow hover:text-white hover:scale-105 hover:shadow-[0_0_20px_rgba(255,197,61,0.25)] transition-all duration-300">
                  NVIDIA
                </span>, and{' '}
                <span className="font-section-heading font-bold text-primary tracking-widest uppercase inline-block border border-frost-border bg-surface/50 px-4 py-1.5 rounded-lg mx-1 my-1 shadow-[inset_0_0_10px_rgba(255,255,255,0.05)] hover:border-accent-green hover:text-white hover:scale-105 hover:shadow-[0_0_20px_rgba(17,255,153,0.25)] transition-all duration-300">
                  HUGGING FACE KEYS
                </span>{' '}
                with free fallback protocols.
              </p>
            </div>
          </div>
        </section>
      </main>

      {/* Footer Component */}
      <footer className="bg-void-black border-t border-frost-border py-16">
        <div className="max-w-container-max mx-auto px-md flex flex-col md:flex-row justify-between items-center gap-8">
          <div className="flex items-center gap-3">
            <Shield className="w-5 h-5 text-on-surface-variant" />
            <span className="font-section-heading text-on-surface text-xl font-bold tracking-tighter">Notary</span>
          </div>

          <a 
            href="https://github.com/Ksalgotra1/Notary/blob/main/LICENSE" 
            target="_blank" 
            rel="noopener noreferrer" 
            className="flex items-center gap-2 text-on-surface-variant hover:text-primary transition-colors font-body-base text-sm"
          >
            <Scale className="w-4 h-4 text-accent-green" />
            <span>MIT License</span>
          </a>

          <div className="flex gap-6">
            <a href="https://github.com/Ksalgotra1/Notary" target="_blank" rel="noopener noreferrer" className="text-on-surface-variant hover:text-primary transition-colors font-body-base text-sm">GitHub</a>
          </div>
        </div>
      </footer>
    </div>
  );
}
