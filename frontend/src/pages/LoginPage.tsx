import LoginForm from "../components/auth/LoginForm";

const LoginPage = () => {
  return (
    <div className="min-h-screen flex">
      {/* Left panel — branding */}
      <div className="hidden lg:flex lg:w-1/2 relative bg-gradient-to-br from-violet-900 via-indigo-900 to-slate-900 flex-col justify-between overflow-hidden p-12">
        {/* Decorative orbs */}
        <div className="absolute -top-32 -left-32 w-96 h-96 rounded-full bg-violet-600/20 blur-3xl pointer-events-none" />
        <div className="absolute top-1/2 -right-24 w-80 h-80 rounded-full bg-indigo-500/20 blur-3xl pointer-events-none" />
        <div className="absolute -bottom-24 left-1/4 w-72 h-72 rounded-full bg-blue-600/15 blur-3xl pointer-events-none" />

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
          <div className="w-10 h-10 rounded-2xl bg-gradient-to-br from-violet-400 to-indigo-500 flex items-center justify-center shadow-xl shadow-violet-900/50">
            <svg className="w-6 h-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z" />
            </svg>
          </div>
          <span className="text-lg font-bold text-white tracking-tight">Auditable</span>
        </div>

        {/* Hero copy */}
        <div className="relative space-y-6">
          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-white/10 border border-white/15 text-violet-200 text-xs font-medium backdrop-blur-sm">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
            AI-Powered Shopify QA
          </div>

          <h2 className="text-4xl font-bold text-white leading-tight">
            Design quality,<br />
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-violet-300 to-indigo-300">
              delivered with precision.
            </span>
          </h2>

          <p className="text-slate-400 text-base leading-relaxed max-w-sm">
            Automate visual, functional, SEO, and accessibility QA across every breakpoint — powered by AI.
          </p>

          {/* Feature pills */}
          <div className="flex flex-wrap gap-2">
            {["Visual Comparison", "Functional Tests", "SEO Audit", "Accessibility"].map((f) => (
              <span key={f} className="px-3 py-1 rounded-full bg-white/8 border border-white/12 text-xs text-slate-300 backdrop-blur-sm">
                {f}
              </span>
            ))}
          </div>
        </div>

        {/* Stat strip */}
        <div className="relative grid grid-cols-3 gap-4">
          {[
            { value: "99%", label: "Issue detection" },
            { value: "3×", label: "Faster QA cycles" },
            { value: "∞", label: "Breakpoints" },
          ].map((s) => (
            <div key={s.label} className="text-center">
              <p className="text-2xl font-bold text-white">{s.value}</p>
              <p className="text-[11px] text-slate-500 mt-0.5">{s.label}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Right panel — form */}
      <div className="flex-1 flex items-center justify-center relative bg-white dark:bg-slate-950 p-8 overflow-hidden">
        {/* Ambient orbs */}
        <div className="absolute top-1/4 right-1/4 w-72 h-72 rounded-full bg-violet-600/10 blur-3xl pointer-events-none" />
        <div className="absolute bottom-1/4 left-1/4 w-64 h-64 rounded-full bg-indigo-600/10 blur-3xl pointer-events-none" />

        <div className="relative w-full max-w-md">
          {/* Mobile logo */}
          <div className="lg:hidden flex items-center gap-2 mb-8">
            <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-violet-500 to-indigo-600 flex items-center justify-center">
              <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z" />
              </svg>
            </div>
            <span className="font-bold text-gray-900 dark:text-white">Auditable</span>
          </div>

          <div className="mb-8">
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Welcome back</h1>
            <p className="text-gray-500 dark:text-slate-400 mt-1 text-sm">Sign in to your account to continue</p>
          </div>

          <LoginForm />
        </div>
      </div>
    </div>
  );
};

export default LoginPage;
