import { motion } from "framer-motion";
import { ArrowUpRight, Play, Zap, Palette, BarChart3, Shield } from "lucide-react";
import { BlurText } from "./components/BlurText";
import { HLSVideo } from "./components/HLSVideo";

function App() {
  return (
    <div className="bg-black text-foreground font-body min-h-screen relative overflow-x-hidden">
      {/* SECTION 1 - NAVBAR */}
      <nav className="fixed top-4 left-0 right-0 z-50 px-6 max-w-7xl mx-auto flex items-center justify-between">
        <div className="w-12 h-12 rounded-full overflow-hidden bg-white/10 flex items-center justify-center">
          <img src="/logo.png" alt="" className="w-full h-full object-cover opacity-0" />
          <div className="absolute text-white font-heading italic text-xl">S</div>
        </div>
        
        <div className="liquid-glass rounded-full px-6 py-2.5 flex items-center gap-6 hidden md:flex">
          {["Home", "Services", "Work", "Process", "Pricing"].map((item) => (
            <a key={item} href="#" className="text-sm font-medium text-foreground/90 hover:text-white transition-colors">
              {item}
            </a>
          ))}
        </div>

        <button className="bg-white text-black px-5 py-2.5 rounded-full text-sm font-medium flex items-center gap-2 hover:bg-white/90 transition-colors">
          Get Started <ArrowUpRight className="w-4 h-4" />
        </button>
      </nav>

      {/* SECTION 2 - HERO */}
      <section className="relative w-full h-[1000px] bg-black overflow-hidden flex flex-col items-center justify-center pt-[150px]">
        {/* Background Video (Local) */}
        <video 
          className="absolute top-[20%] w-full h-auto object-contain z-0"
          autoPlay 
          loop 
          muted 
          playsInline
          src="/hero-video.mp4"
        />
        {/* Overlays */}
        <div className="absolute inset-0 bg-black/5 z-0"></div>
        <div className="absolute bottom-0 left-0 right-0 z-[1] h-[300px] bg-gradient-to-b from-transparent to-black"></div>

        {/* Content */}
        <div className="relative z-10 flex flex-col items-center w-full max-w-5xl px-6 text-center">
          <div className="liquid-glass rounded-full p-1 pr-4 flex items-center gap-3 mb-8">
            <span className="bg-white text-black text-xs font-bold px-3 py-1 rounded-full uppercase tracking-wider">New</span>
            <span className="text-sm text-white/90">Introducing AI-powered web design.</span>
          </div>

          <BlurText 
            text="The Website Your Brand Deserves" 
            className="text-6xl md:text-7xl lg:text-[5.5rem] font-heading italic text-foreground leading-[0.8] tracking-[-4px] mb-8"
            delay={1}
          />

          <motion.p 
            initial={{ opacity: 0, filter: "blur(10px)", y: 20 }}
            animate={{ opacity: 1, filter: "blur(0px)", y: 0 }}
            transition={{ duration: 0.8, delay: 0.8 }}
            className="text-lg md:text-xl text-white/60 max-w-2xl mx-auto mb-12"
          >
            Stunning design. Blazing performance. Built by AI, refined by experts. This is web design, wildly reimagined.
          </motion.p>

          <motion.div 
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 1.1 }}
            className="flex items-center gap-6"
          >
            <button className="liquid-glass-strong rounded-full px-8 py-4 flex items-center gap-2 text-white hover:bg-white/5 transition-colors">
              Get Started <ArrowUpRight className="w-5 h-5" />
            </button>
            <button className="flex items-center gap-2 text-white/80 hover:text-white transition-colors group">
              <span className="w-12 h-12 rounded-full border border-white/20 flex items-center justify-center group-hover:border-white/40 transition-colors">
                <Play className="w-4 h-4 fill-current" />
              </span>
              Watch the Film
            </button>
          </motion.div>
        </div>

        {/* SECTION 3 - PARTNERS BAR */}
        <div className="mt-auto pb-8 pt-16 z-10 relative flex flex-col items-center w-full">
          <div className="liquid-glass rounded-full px-4 py-1.5 text-xs font-medium text-white mb-8">
            Trusted by the teams behind
          </div>
          <div className="flex flex-wrap justify-center items-center gap-8 md:gap-12 lg:gap-16 px-6">
            {["Stripe", "Vercel", "Linear", "Notion", "Figma"].map((partner) => (
              <span key={partner} className="text-2xl md:text-3xl font-heading italic text-white/80">
                {partner}
              </span>
            ))}
          </div>
        </div>
      </section>

      {/* SECTION 4 - START SECTION */}
      <section className="relative w-full min-h-[700px] flex items-center justify-center py-32 px-6 md:px-16 lg:px-24">
        <HLSVideo 
          src="https://stream.mux.com/9JXDljEVWYwWu01PUkAemafDugK89o01BR6zqJ3aS9u00A.m3u8"
          className="absolute inset-0 w-full h-full object-cover z-0"
        />
        <div className="absolute top-0 left-0 right-0 h-[200px] bg-gradient-to-b from-black to-transparent z-[1]"></div>
        <div className="absolute bottom-0 left-0 right-0 h-[200px] bg-gradient-to-t from-black to-transparent z-[1]"></div>

        <div className="relative z-10 flex flex-col items-center text-center max-w-3xl min-h-[500px] justify-center">
          <div className="liquid-glass rounded-full px-3.5 py-1 text-xs font-medium text-white font-body inline-block mb-6">
            How It Works
          </div>
          <h2 className="text-4xl md:text-5xl lg:text-6xl font-heading italic text-white tracking-tight leading-[0.9] mb-6">
            You dream it. We ship it.
          </h2>
          <p className="text-white/60 font-body font-light text-lg md:text-xl mb-10">
            Share your vision. Our AI handles the rest—wireframes, design, code, launch. All in days, not quarters.
          </p>
          <button className="liquid-glass-strong rounded-full px-8 py-4 flex items-center gap-2 text-white hover:bg-white/5 transition-colors">
            Get Started <ArrowUpRight className="w-5 h-5" />
          </button>
        </div>
      </section>

      {/* SECTION 5 - FEATURES CHESS */}
      <section className="py-24 px-6 md:px-16 lg:px-24 max-w-7xl mx-auto">
        <div className="text-center mb-24">
          <div className="liquid-glass rounded-full px-3.5 py-1 text-xs font-medium text-white font-body inline-block mb-4">
            Capabilities
          </div>
          <h2 className="text-4xl md:text-5xl lg:text-6xl font-heading italic text-white tracking-tight leading-[0.9]">
            Pro features. Zero complexity.
          </h2>
        </div>

        {/* Row 1 */}
        <div className="flex flex-col lg:flex-row items-center gap-16 mb-24">
          <div className="flex-1 text-left">
            <h3 className="text-3xl md:text-4xl font-heading italic text-white leading-[1] mb-6">
              Designed to convert.<br/>Built to perform.
            </h3>
            <p className="text-white/60 mb-8 max-w-md">
              Every pixel is intentional. Our AI studies what works across thousands of top sites—then builds yours to outperform them all.
            </p>
            <button className="liquid-glass-strong rounded-full px-6 py-3 text-sm text-white hover:bg-white/5 transition-colors">
              Learn more
            </button>
          </div>
          <div className="flex-1 w-full relative">
            <div className="liquid-glass rounded-2xl overflow-hidden aspect-video flex items-center justify-center bg-white/5">
              <span className="text-white/20">UI Interactive GIF</span>
            </div>
          </div>
        </div>

        {/* Row 2 */}
        <div className="flex flex-col lg:flex-row-reverse items-center gap-16">
          <div className="flex-1 lg:pl-16 text-left">
            <h3 className="text-3xl md:text-4xl font-heading italic text-white leading-[1] mb-6">
              It gets smarter.<br/>Automatically.
            </h3>
            <p className="text-white/60 mb-8 max-w-md">
              Your site evolves on its own. AI monitors every click, scroll, and conversion—then optimizes in real time. No manual updates. Ever.
            </p>
            <button className="liquid-glass rounded-full px-6 py-3 text-sm text-white hover:bg-white/5 transition-colors">
              See how it works
            </button>
          </div>
          <div className="flex-1 w-full relative">
            <div className="liquid-glass rounded-2xl overflow-hidden aspect-video flex items-center justify-center bg-white/5">
              <span className="text-white/20">Optimization Flow</span>
            </div>
          </div>
        </div>
      </section>

      {/* SECTION 6 - FEATURES GRID */}
      <section className="py-24 px-6 md:px-16 lg:px-24 max-w-7xl mx-auto">
        <div className="text-center mb-16">
          <div className="liquid-glass rounded-full px-3.5 py-1 text-xs font-medium text-white font-body inline-block mb-4">
            Why Us
          </div>
          <h2 className="text-4xl md:text-5xl lg:text-6xl font-heading italic text-white tracking-tight leading-[0.9]">
            The difference is everything.
          </h2>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 text-left">
          {[
            { icon: Zap, title: "Days, Not Months", desc: "Concept to launch at a pace that redefines fast." },
            { icon: Palette, title: "Obsessively Crafted", desc: "Every detail considered. Every element refined." },
            { icon: BarChart3, title: "Built to Convert", desc: "Layouts informed by data. Decisions backed by performance." },
            { icon: Shield, title: "Secure by Default", desc: "Enterprise-grade protection comes standard." },
          ].map((feature, i) => (
            <div key={i} className="liquid-glass rounded-2xl p-6 flex flex-col gap-4">
              <div className="liquid-glass-strong rounded-full w-10 h-10 flex items-center justify-center mb-2">
                <feature.icon className="w-5 h-5 text-white" />
              </div>
              <h3 className="text-xl font-heading italic text-white">{feature.title}</h3>
              <p className="text-white/60 font-body font-light text-sm">{feature.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* SECTION 7 - STATS */}
      <section className="relative w-full py-32 px-6 flex items-center justify-center min-h-[500px]">
        <HLSVideo 
          src="https://stream.mux.com/NcU3HlHeF7CUL86azTTzpy3Tlb00d6iF3BmCdFslMJYM.m3u8"
          className="absolute inset-0 w-full h-full object-cover z-0 mix-blend-screen"
          style={{ filter: "saturate(0) opacity(0.5)" }}
        />
        <div className="absolute top-0 left-0 right-0 h-[200px] bg-gradient-to-b from-black to-transparent z-[1]"></div>
        <div className="absolute bottom-0 left-0 right-0 h-[200px] bg-gradient-to-t from-black to-transparent z-[1]"></div>

        <div className="relative z-10 w-full max-w-5xl">
          <div className="liquid-glass rounded-3xl p-12 md:p-16 grid grid-cols-2 lg:grid-cols-4 gap-8 text-center mx-auto">
            {[
              { val: "200+", label: "Sites launched" },
              { val: "98%", label: "Client satisfaction" },
              { val: "3.2x", label: "More conversions" },
              { val: "5 days", label: "Average delivery" },
            ].map((stat, i) => (
              <div key={i} className="flex flex-col gap-2">
                <div className="text-4xl md:text-5xl lg:text-6xl font-heading italic text-white">{stat.val}</div>
                <div className="text-white/60 font-body font-light text-sm">{stat.label}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* SECTION 8 - TESTIMONIALS */}
      <section className="py-24 px-6 md:px-16 lg:px-24 max-w-7xl mx-auto">
        <div className="text-center mb-16">
          <div className="liquid-glass rounded-full px-3.5 py-1 text-xs font-medium text-white font-body inline-block mb-4">
            What They Say
          </div>
          <h2 className="text-4xl md:text-5xl lg:text-6xl font-heading italic text-white tracking-tight leading-[0.9]">
            Don't take our word for it.
          </h2>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 text-left">
          {[
            { name: "Sarah Chen", role: "CEO Luminary", quote: "\"A complete rebuild in five days that looked like it took five months. The ROI has been absurd.\"" },
            { name: "Marcus Webb", role: "Head of Growth Arcline", quote: "\"Conversions up 4x purely from the layout and performance optimizations their AI dictated. Flawless.\"" },
            { name: "Elena Voss", role: "Brand Director Helix", quote: "\"They didn't just design our site, they captured our exact brand vibe perfectly. The liquid glass aesthetic is breathtaking.\"" },
          ].map((t, i) => (
            <div key={i} className="liquid-glass rounded-2xl p-8 flex flex-col justify-between min-h-[200px]">
              <p className="text-white/80 font-body font-light text-sm italic mb-6 leading-relaxed">
                {t.quote}
              </p>
              <div>
                <div className="text-white font-body font-medium text-sm">{t.name}</div>
                <div className="text-white/50 font-body font-light text-xs">{t.role}</div>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* SECTION 9 - CTA FOOTER */}
      <section className="relative w-full pt-32 flex flex-col min-h-[600px] justify-end">
        <HLSVideo 
          src="https://stream.mux.com/8wrHPCX2dC3msyYU9ObwqNdm00u3ViXvOSHUMRYSEe5Q.m3u8"
          className="absolute inset-0 w-full h-full object-cover z-0 mt-32 mix-blend-screen"
        />
        <div className="absolute top-0 left-0 right-0 h-[200px] bg-gradient-to-b from-black to-transparent z-[1]"></div>
        <div className="absolute bottom-0 left-0 right-0 h-[300px] bg-gradient-to-t from-black to-transparent z-[1]"></div>

        <div className="relative z-10 flex flex-col items-center text-center px-6 w-full pb-12">
          <h2 className="text-5xl md:text-6xl lg:text-7xl font-heading italic text-white tracking-tight leading-[0.9] mb-6">
            Your next website starts here.
          </h2>
          <p className="text-white/60 font-body text-lg mb-10 max-w-md mx-auto">
            Book a free strategy call. See what AI-powered design can do.
          </p>
          
          <div className="flex flex-col sm:flex-row items-center gap-4 mb-24">
            <button className="liquid-glass-strong rounded-full px-8 py-4 text-white font-medium hover:bg-white/5 transition-colors">
              Book a Call
            </button>
            <button className="bg-white text-black rounded-full px-8 py-4 font-medium hover:bg-white/90 transition-colors">
              View Pricing
            </button>
          </div>

          <footer className="w-full max-w-7xl mx-auto pt-8 border-t border-white/10 flex flex-col md:flex-row items-center justify-between text-white/40 text-xs gap-4 relative z-20">
            <div>© 2026 Studio</div>
            <div className="flex gap-6">
              <a href="#" className="hover:text-white/80 transition-colors">Privacy</a>
              <a href="#" className="hover:text-white/80 transition-colors">Terms</a>
              <a href="#" className="hover:text-white/80 transition-colors">Contact</a>
            </div>
          </footer>
        </div>
      </section>
    </div>
  );
}

export default App;
