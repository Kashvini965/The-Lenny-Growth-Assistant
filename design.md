# UI/UX design

## Information architecture

- **Conversation sidebar:** The Lenny Growth Assistant identity, new-chat action, searchable chronological conversation history, timestamps, delete controls, API connectivity, and a collapsible desktop rail/mobile drawer.
- **Chat workspace:** session title, provider/model and transcript-use settings, message timeline, citations, composer, and request/error states.
- **Empty workspace:** editorial welcome state with three actionable prompt starters. Selecting a starter fills the real composer; it does not create a sample message or send a request.
- **Message actions:** assistant answers can be copied or asked again. “Ask again” submits the original user message as a new turn; it is not an in-place model regeneration.
- **Writing/artifact workspace:** actions for an essay, the Ship 30 for 30 skill, and Markdown or HTML/CSS output. The artifact is shown alongside the conversation, not in an external app.

## Interaction states

- Initial empty state explains the assistant's transcript-grounded purpose without inventing example messages.
- Session and provider loading states are visible; unavailable providers are not presented as ready.
- The sidebar connectivity label reflects API reachability, not model availability. Provider readiness is shown separately with the selected provider/model and its reported status.
- Sending disables duplicate submission and shows a generation indicator.
- Structured network/provider errors remain visible and offer retry for the failed chat request.
- An empty knowledge base or insufficient retrieval is communicated as an evidence limitation, not a generic AI answer.
- Citations expand to show the transcript title, source, URL, and excerpt.
- Artifact generation exposes a pending state and distinct Markdown/HTML display; preview errors do not silently fall back to raw HTML.
- Session creation, selection, and deletion update history without conflating conversation context.
- If the backend returns a provider, retrieval, or database error, the UI shows the API message and does not synthesize a success response. Chat retry repeats the saved request against its original session/provider configuration.

## Responsive behavior and accessibility

The desktop sidebar is sized responsively to approximately 280–320px and can collapse to a compact icon rail; on narrow screens it becomes a dismissible navigation drawer and prompt starters stack vertically. Branding/actions and the connection/footer status stay outside the independently scrollable history region. The main conversation content has its own vertical scroll area; the page wrapper prevents body-level scrolling, while the header and composer remain in place. Flex/grid children use constrained minimum sizes to avoid overflow. The layout was checked at viewport widths from 390px through 1600px; browser zoom levels were not separately measured in this verification.

Layout changes preserve provider controls, composer, and artifact content. Controls use native buttons/selects/inputs, labels and accessible names; alerts use a live error role; keyboard Enter sends and Shift+Enter inserts a newline. Ctrl/⌘+K starts a new conversation. Motion is subtle and a `prefers-reduced-motion` override minimizes animation, transitions, and smooth scrolling.

The frontend is served by Vite at `http://localhost:5173` for local development and by the Compose-built static frontend at `http://localhost:4173`. `VITE_API_BASE_URL` configures the backend origin; provider secrets are never part of the frontend environment.

## Artifact safety decision

Markdown is rendered as text/Markdown, never through arbitrary raw HTML. HTML artifacts are sanitized on the server, returned with an explicit restrictive CSP, and displayed in an iframe with an empty `sandbox` attribute. Scripts, forms, embeds, SVG, external images, and network connections are blocked. Inline CSS is restricted to an allowlist of properties; external style sheets and imports are removed.

## Visual direction

Use The Lenny Growth Assistant identity: a deep midnight-teal navigation rail, cool neutral canvas, restrained teal and amber accents, and compact editorial typography. The conversation surface has clear role hierarchy, quiet suggestion cards, readable long-form answers, and a floating composer. Avoid stock chat decoration; preserve functional density rather than ornamental animation.

## Workspace background illustration

A separate `WorkspaceBackground` decorative layer sits behind the main workspace content. Its inline SVG combines a white-to-sky-blue wash, upper-left abstract curves, upper-right dot grid, silver-blue podcast microphone, connected assistant hub and five translucent capability cards, growth/audio motifs, and a quiet desktop vignette with notebook, pen, mug, and plant. A handwritten-style growth motto is intentionally low contrast. The center wash protects content contrast; the illustration is `aria-hidden`, pointer-transparent, uses no external image request or animation, and becomes more subdued/cropped at tablet and mobile widths. It does not replace the functional prompt suggestions or change the existing chat controls.

## Verification boundary

The current local check confirmed the Vite page and API responded, and the layout's viewport responsiveness had previously been checked from 390px to 1600px. Automated frontend validation consists of TypeScript project checking and the Vite production build; there is no frontend test or lint script. Live provider-dependent UI states could not be exercised because Ollama was unavailable and cloud providers were unconfigured.
