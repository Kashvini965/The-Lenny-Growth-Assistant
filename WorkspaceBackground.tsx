export default function WorkspaceBackground() {
  return (
    <div className="workspace-background" aria-hidden="true">
      <span className="bg-circle bg-circle-a" />
      <span className="bg-circle bg-circle-b" />
      <span className="bg-circle bg-circle-c" />
      <svg
        className="workspace-illustration"
        viewBox="0 0 1600 1000"
        preserveAspectRatio="xMidYMid slice"
        focusable="false"
      >
        <defs>
          <radialGradient id="wb-center-glow" cx="50%" cy="48%" r="62%">
            <stop offset="0" stopColor="#ffffff" stopOpacity=".92" />
            <stop offset=".6" stopColor="#ffffff" stopOpacity=".55" />
            <stop offset="1" stopColor="#ffffff" stopOpacity="0" />
          </radialGradient>
          <linearGradient id="wb-laptop" x1="0" y1="0" x2="1" y2="1">
            <stop stopColor="#6fa4e6" />
            <stop offset="1" stopColor="#3363ac" />
          </linearGradient>
          <linearGradient id="wb-screen" x1="0" y1="0" x2="0" y2="1">
            <stop stopColor="#e7f3ff" />
            <stop offset="1" stopColor="#c7e0fb" />
          </linearGradient>
          <linearGradient id="wb-plant" x1="0" y1="0" x2="0" y2="1">
            <stop stopColor="#7fb79a" />
            <stop offset="1" stopColor="#4f9878" />
          </linearGradient>
          <linearGradient id="wb-bar" x1="0" y1="1" x2="0" y2="0">
            <stop stopColor="#8fbcff" stopOpacity=".22" />
            <stop offset="1" stopColor="#4f8ff7" stopOpacity=".5" />
          </linearGradient>
          <filter id="wb-soft" x="-40%" y="-40%" width="180%" height="190%">
            <feDropShadow dx="0" dy="12" stdDeviation="16" floodColor="#6f9dd0" floodOpacity=".2" />
          </filter>
          <pattern id="wb-dots" width="20" height="20" patternUnits="userSpaceOnUse">
            <circle cx="3" cy="3" r="1.8" fill="#5f93d0" fillOpacity=".42" />
          </pattern>
        </defs>

        <ellipse cx="820" cy="500" rx="640" ry="430" fill="url(#wb-center-glow)" />

        {/* Dotted pattern, upper-right */}
        <rect x="1262" y="48" width="266" height="196" fill="url(#wb-dots)" opacity=".85" />

        {/* Flowing waves across the lower half */}
        <g className="illustration-waves" fill="none" stroke="#9cc6ec" strokeLinecap="round" opacity=".3">
          <path d="M-40 735c150-40 300-40 450 6s300 46 450 0 300-46 450 0 300 40 450 6" strokeWidth="2.4" />
          <path d="M-60 786c160-42 320-42 480 4s320 46 480 0 320-46 480 0 320 42 480 6" strokeWidth="1.9" />
          <path d="M-80 834c170-44 340-44 510 2s340 44 510 0 340-44 510 0 340 44 510 2" strokeWidth="1.5" opacity=".8" />
        </g>

        {/* Growth curve + translucent ascending bars, lower-right */}
        <g className="growth-viz">
          <rect x="1052" y="902" width="20" height="34" rx="5" fill="url(#wb-bar)" />
          <rect x="1090" y="872" width="20" height="64" rx="5" fill="url(#wb-bar)" />
          <rect x="1128" y="836" width="20" height="100" rx="5" fill="url(#wb-bar)" />
          <rect x="1166" y="800" width="20" height="136" rx="5" fill="url(#wb-bar)" />
          <rect x="1204" y="758" width="20" height="178" rx="5" fill="url(#wb-bar)" />
          <rect x="1242" y="716" width="20" height="220" rx="5" fill="url(#wb-bar)" />
          <rect x="1280" y="672" width="20" height="264" rx="5" fill="url(#wb-bar)" />
          <rect x="1318" y="628" width="20" height="308" rx="5" fill="url(#wb-bar)" />
          <path d="M1040 898c120-30 210-90 300-166s150-130 244-176" fill="none" stroke="#3f7fd0" strokeWidth="3.2" strokeLinecap="round" opacity=".55" />
          <path d="M1578 552l14 4-6 14" fill="none" stroke="#3f7fd0" strokeWidth="3.2" strokeLinecap="round" strokeLinejoin="round" opacity=".55" />
        </g>

        {/* Abstract AI waveform near the bottom */}
        <g className="ai-waveform" fill="none" stroke="#6aa3dd" strokeLinecap="round" opacity=".36">
          <path d="M520 940v-26" strokeWidth="3" />
          <path d="M548 952v-52" strokeWidth="3" />
          <path d="M576 962v-78" strokeWidth="3" />
          <path d="M604 950v-54" strokeWidth="3" />
          <path d="M632 966v-92" strokeWidth="3" />
          <path d="M660 942v-40" strokeWidth="3" />
          <path d="M688 958v-70" strokeWidth="3" />
          <path d="M716 944v-44" strokeWidth="3" />
          <path d="M744 968v-96" strokeWidth="3" />
          <path d="M772 948v-52" strokeWidth="3" />
          <path d="M800 938v-32" strokeWidth="3" />
        </g>

        {/* Soft translucent growth ring */}
        <g className="ambient-rings" fill="none" stroke="#b0d2f1" opacity=".45">
          <circle cx="1150" cy="250" r="120" strokeWidth="1.6" />
          <circle cx="1150" cy="250" r="166" strokeWidth="1.2" strokeDasharray="4 12" />
        </g>

        {/* Decorative workspace illustration, bottom-left */}
        <g className="desk-illustration" filter="url(#wb-soft)" opacity=".72">
          <ellipse cx="248" cy="952" rx="300" ry="34" fill="#bcd9f1" fillOpacity=".3" />

          <g transform="rotate(-7 300 900)">
            <rect x="196" y="862" width="150" height="104" rx="8" fill="#ffffff" stroke="#bcd6ec" strokeWidth="2.5" />
            <path d="M218 890h106M218 908h96M218 926h74" stroke="#a9cae8" strokeWidth="4" strokeLinecap="round" />
            <rect x="188" y="862" width="14" height="104" rx="6" fill="#4f8ff7" opacity=".85" />
          </g>
          <path d="M382 872l88 60" stroke="#7ba0c6" strokeWidth="9" strokeLinecap="round" />
          <path d="M466 928l16 12-18 6z" fill="#f0b478" />
          <path d="M378 866l14 4 6 18-14 6z" fill="#c9dcf0" />

          <g transform="translate(392 866)">
            <rect x="0" y="0" width="66" height="72" rx="12" fill="#ffffff" stroke="#c3d9ea" strokeWidth="2.5" />
            <path d="M66 18c24-2 24 34 0 32" fill="none" stroke="#c3d9ea" strokeWidth="9" />
            <ellipse cx="33" cy="4" rx="30" ry="9" fill="#eaf4ff" stroke="#c3d9ea" strokeWidth="2" />
            <path d="M33 20c-8 8-8 16 0 22m14-20c-7 8-7 14 0 20" fill="none" stroke="#b9d6ef" strokeWidth="3" strokeLinecap="round" opacity=".8" />
          </g>

          <g className="laptop">
            <rect x="70" y="744" width="230" height="150" rx="16" fill="#ffffff" stroke="#bcd6ec" strokeWidth="3" />
            <rect x="88" y="762" width="194" height="114" rx="10" fill="url(#wb-screen)" />
            <path d="M112 852l-24 24m0 0l14-2m-14 2l2-14" fill="none" stroke="#4f8ff7" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" opacity=".8" />
            <rect x="112" y="838" width="60" height="6" rx="3" fill="#7fb0ea" opacity=".7" />
            <rect x="112" y="850" width="96" height="6" rx="3" fill="#a4c9f2" opacity=".6" />
            <path d="M40 894h290l-24 34H64z" fill="url(#wb-laptop)" />
            <rect x="150" y="904" width="70" height="7" rx="3.5" fill="#ffffff" opacity=".65" />
          </g>

          <g className="plant" transform="translate(6 700)">
            <g fill="url(#wb-plant)" stroke="#3f8f6f" strokeWidth="2">
              <path d="M54 138c-30-30-10-58 19-70 6 28 2 52-19 70z" />
              <path d="M66 132c-6-44 18-66 42-70 0 34-14 57-42 70z" />
              <path d="M60 140c22-37 48-40 67-27-14 24-36 35-67 27z" />
            </g>
            <path d="M60 140v82m0-46l-16-20m18 8l24-28" fill="none" stroke="#4f9878" strokeWidth="4" strokeLinecap="round" />
            <path d="M30 218h64l-8 44H38z" fill="#ffffff" stroke="#bcd6ec" strokeWidth="2.5" />
          </g>
        </g>
      </svg>
      <div className="workspace-background-wash" />
    </div>
  );
}
