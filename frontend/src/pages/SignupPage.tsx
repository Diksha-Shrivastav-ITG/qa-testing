import SignupForm from "../components/auth/SignupForm";

const steps = [
  { icon: "M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z", text: "Connect your Shopify store" },
  { icon: "M6.827 6.175A2.31 2.31 0 015.186 7.23c-.38.054-.757.112-1.134.175C2.999 7.58 2.25 8.507 2.25 9.574V18a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18V9.574c0-1.067-.75-1.994-1.802-2.169a47.865 47.865 0 00-1.134-.175 2.31 2.31 0 01-1.64-1.055l-.822-1.316a2.192 2.192 0 00-1.736-1.039 48.774 48.774 0 00-5.232 0 2.192 2.192 0 00-1.736 1.039l-.821 1.316z", text: "Capture screenshots at every breakpoint" },
  { icon: "M11.48 3.499a.562.562 0 011.04 0l2.125 5.111a.563.563 0 00.475.345l5.518.442c.499.04.701.663.321.988l-4.204 3.602a.563.563 0 00-.182.557l1.285 5.385a.562.562 0 01-.84.61l-4.725-2.885a.563.563 0 00-.586 0L6.982 20.54a.562.562 0 01-.84-.61l1.285-5.386a.562.562 0 00-.182-.557l-4.204-3.602a.563.563 0 01.321-.988l5.518-.442a.563.563 0 00.475-.345L11.48 3.5z", text: "Get AI-powered issue reports instantly" },
];

const SignupPage = () => {
  return (
    <div className="min-h-screen flex">
      {/* Left panel — branding */}
      <div className="hidden lg:flex lg:w-1/2 relative bg-gradient-to-br from-slate-900 via-indigo-950 to-violet-900 flex-col justify-between overflow-hidden p-12">
        {/* Decorative orbs */}
        <div className="absolute -top-24 -right-24 w-96 h-96 rounded-full bg-indigo-600/20 blur-3xl pointer-events-none" />
        <div className="absolute bottom-1/4 -left-24 w-80 h-80 rounded-full bg-violet-500/20 blur-3xl pointer-events-none" />
        <div className="absolute -bottom-32 right-1/3 w-72 h-72 rounded-full bg-blue-600/15 blur-3xl pointer-events-none" />

        {/* Grid overlay */}
        <div
          className="absolute inset-0 opacity-[0.04]"
          style={{
            backgroundImage:
              "linear-gradient(rgba(255,255,255,0.3) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.3) 1px, transparent 1px)",
            backgroundSize: "40px 40px",
          }}
        />

        {/* Logo */}
        <div className="relative flex items-center gap-3">
          <img src="/logo.png" alt="Auditable ITG" className="h-8 w-auto brightness-0 invert" />
          <span className="text-lg font-bold text-white tracking-tight">Auditable ITG</span>
        </div>

        {/* Hero copy */}
        <div className="relative space-y-6">
          <h2 className="text-4xl font-bold text-white leading-tight">
            Start testing smarter<br />
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-indigo-300 to-violet-300">
              in minutes.
            </span>
          </h2>
          <p className="text-slate-400 text-base leading-relaxed max-w-sm">
            Set up your workspace, connect a Shopify store, and let AI handle the heavy lifting.
          </p>

          {/* Steps */}
          <div className="space-y-4 pt-2">
            {steps.map((step, i) => (
              <div key={i} className="flex items-center gap-4">
                <div className="w-8 h-8 rounded-xl bg-white/10 border border-white/15 flex items-center justify-center shrink-0">
                  <svg className="w-4 h-4 text-violet-300" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d={step.icon} />
                  </svg>
                </div>
                <p className="text-sm text-slate-300">{step.text}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Trust strip */}
        <div className="relative">
          <p className="text-xs text-slate-500 mb-3">Trusted by Shopify agencies worldwide</p>
          <div className="flex gap-2 flex-wrap">
            {["SOC 2", "GDPR Ready", "99.9% Uptime"].map((badge) => (
              <span key={badge} className="px-3 py-1 rounded-full bg-white/8 border border-white/12 text-xs text-slate-400">
                {badge}
              </span>
            ))}
          </div>
        </div>
      </div>

      {/* Right panel — form */}
      <div className="flex-1 flex items-center justify-center relative bg-white dark:bg-slate-950 p-8 overflow-hidden">
        {/* Ambient orbs */}
        <div className="absolute top-1/3 right-1/4 w-72 h-72 rounded-full bg-indigo-600/10 blur-3xl pointer-events-none" />
        <div className="absolute bottom-1/3 left-1/4 w-64 h-64 rounded-full bg-violet-600/10 blur-3xl pointer-events-none" />

        <div className="relative w-full max-w-md">
          {/* Mobile logo */}
          <div className="lg:hidden flex items-center gap-2 mb-8">
            <img src="/logo.png" alt="Auditable ITG" className="h-7 w-auto" />
            <span className="font-bold text-gray-900 dark:text-white">Auditable ITG</span>
          </div>

          <div className="mb-8">
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Create your account</h1>
            <p className="text-gray-500 dark:text-slate-400 mt-1 text-sm">Get started for free — no credit card required</p>
          </div>

          <SignupForm />
        </div>
      </div>
    </div>
  );
};

export default SignupPage;
