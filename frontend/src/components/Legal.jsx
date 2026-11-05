import { useEffect } from "react";
import Icon from "../icons.jsx";
import { Logo, ThemeSwitch } from "./Shell.jsx";

/*
  The privacy policy (/privacy) and terms of use (/terms).
  Written to match what Cashwise actually does with data. Change CONTACT_EMAIL to the address
  people should write to about their data.
*/
export const CONTACT_EMAIL = "your-email@example.com";
const UPDATED = "5 November 2026";

function Privacy() {
  return (
    <>
      <h1>Privacy policy</h1>
      <p className="lg-meta">Last updated {UPDATED}</p>
      <p>Cashwise is a cash-flow forecasting tool for small businesses. This page explains what information it keeps,
        why, who it is shared with, and the choices you have. We keep only what the app needs to work, and we don't sell
        your information or use it for advertising.</p>

      <h2>What we collect</h2>
      <h3>Your account</h3>
      <ul>
        <li><strong>Name and email address</strong>, which you give when you create an account.</li>
        <li><strong>Your password</strong>, which is never stored as typed: we keep only a one-way hash (PBKDF2-SHA256).</li>
        <li><strong>If you sign in with Google, GitHub or Apple</strong>: your name, your email address and that service's
          account ID, so we can recognise you next time. We ask only for the basic profile and email permissions and get
          no access to your files, contacts or anything else in those accounts.</li>
      </ul>
      <h3>Your business records</h3>
      <ul>
        <li>The business details you enter (name, city, what you sell) and the records you upload: customers, suppliers,
          invoices, payments, bills, expenses and history notes. These may include names and contact people of your
          customers and suppliers, so please upload only what you're allowed to share.</li>
        <li>What you do in the app that affects your numbers or reports: bank balances you type in, settings, outcomes
          you record, reports you make, links you share, and the audit trail of these changes.</li>
      </ul>
      <h3>What your browser keeps</h3>
      <p>Cashwise doesn't use advertising or tracking cookies. Your browser's local storage keeps your sign-in token,
        the business you last opened, your light or dark theme, and which alerts and notifications you've seen or hidden.
        During Google, GitHub or Apple sign-in, a short-lived cookie checks that the sign-in really started on this site.</p>
      <h3>Server logs</h3>
      <p>Like any website, the server records basic request information (the page or action, the time, whether it worked)
        to keep the service running and fix problems.</p>

      <h2>How we use it</h2>
      <ul>
        <li>To sign you in and keep each business's records separate.</li>
        <li>To work out your forecasts, alerts and reports from your own records.</li>
        <li>To answer the questions you ask the AI agent, and to remember outcomes so later answers fit your business.</li>
        <li>To send reports by email when you or a schedule you set up asks for it.</li>
      </ul>
      <p>We don't use your records to train AI models, and we don't share them with anyone except the services below,
        which are needed to run the features you use.</p>

      <h2>Services that help run Cashwise</h2>
      <ul>
        <li><strong>Render</strong> hosts the website and stores the databases.</li>
        <li><strong>Groq</strong> runs the AI model. When you ask the agent a question, the question and the relevant
          figures from your forecast are sent to Groq to write the answer.</li>
        <li><strong>Hindsight by Vectorize</strong> stores the agent's long-term memory: history notes you upload and
          outcomes you record, kept in a separate memory bank for each business.</li>
        <li><strong>Google, GitHub and Apple</strong>, only if you choose to sign in with them.</li>
        <li><strong>An email provider</strong>, only when reports are emailed. Recipients get the figures in the email
          and a read-only link.</li>
      </ul>

      <h2>Shared report links</h2>
      <p>When you make a read-only link, anyone who has it can see that one report, and nothing else in your business.
        Links can't be guessed, can expire, and can be turned off at any time on the Shared links page. Each time one is
        opened, it's recorded in your audit trail.</p>

      <h2>How long we keep it, and your choices</h2>
      <ul>
        <li>Your records stay until you delete them. You can clear any type of record on the Your data page, or delete a
          business and everything in it.</li>
        <li>You can delete reports and turn off shared links whenever you like.</li>
        <li>To get a copy of your information or have your account deleted, email us at the address below and we'll do
          it within 30 days.</li>
      </ul>

      <h2>Security</h2>
      <p>Each business has its own separate database, connections use HTTPS, passwords are hashed, and sign-in tokens
        expire. No system is perfectly secure, so please use a strong password and don't share your account.</p>

      <h2>Children</h2>
      <p>Cashwise is a business tool for adults and is not meant for anyone under 18.</p>

      <h2>Changes</h2>
      <p>If we change this policy, we'll update the date at the top. Important changes will be shown in the app.</p>

      <h2>Contact</h2>
      <p>Questions about your data: <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a></p>
    </>
  );
}

function Terms() {
  return (
    <>
      <h1>Terms of use</h1>
      <p className="lg-meta">Last updated {UPDATED}</p>
      <p>By using Cashwise you agree to these terms. If you don't agree, please don't use it.</p>

      <h2>What Cashwise is</h2>
      <p>Cashwise forecasts your cash flow from the records you upload and suggests things you could do. Forecasts are
        estimates based on past payment habits; they can be wrong, and they are <strong>not financial, tax, legal or
        investment advice</strong>. Decisions about your business are yours, so check important figures yourself
        before acting on them.</p>

      <h2>Your account and your data</h2>
      <ul>
        <li>Keep your sign-in details safe. You're responsible for what happens in your account.</li>
        <li>Your records stay yours. You give us permission to store and process them only to provide the service, as
          described in the <a href="/privacy">privacy policy</a>.</li>
        <li>Upload only records you're allowed to use, and don't upload anything unlawful or harmful.</li>
      </ul>

      <h2>Fair use</h2>
      <p>Don't try to break, overload or get around the security of the service, access other people's businesses, or
        use it to send spam. We may suspend accounts that do.</p>

      <h2>The demo business</h2>
      <p>The demo business, Malabar Electronics, is made up and shared by everyone who opens it. Changes made there may
        be seen by others and are reset from time to time, so don't put real information in it.</p>

      <h2>Availability</h2>
      <p>We work to keep Cashwise running, but it's provided "as is", without guarantees that it will always be available
        or error-free. To the extent the law allows, we aren't liable for losses that come from using it or relying on
        its forecasts.</p>

      <h2>Changes and ending</h2>
      <p>We may update these terms; the date at the top shows the latest version. You can stop using Cashwise and delete
        your businesses at any time.</p>

      <h2>Contact</h2>
      <p><a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a></p>
    </>
  );
}

export default function Legal({ page, dark, setDark, onHome, onSignIn, signedIn }) {
  useEffect(() => { window.scrollTo({ top: 0 }); }, [page]);
  const go = (path) => (e) => { e.preventDefault(); window.history.pushState(null, "", path); window.dispatchEvent(new PopStateEvent("popstate")); };
  return (
    <div className="lg">
      <header className="lg-top">
        <a className="lp-brand" href="/" onClick={(e) => { e.preventDefault(); onHome(); }}>
          <Logo on="auto" size={32} /><span>Cashwise</span>
        </a>
        <div className="lg-top-actions">
          <ThemeSwitch dark={dark} setDark={setDark} />
          <button className="lp-btn" onClick={onSignIn}>{signedIn ? "Open dashboard" : "Sign in"} <Icon name="arrowUpRight" size={15} stroke={2.4} /></button>
        </div>
      </header>
      <main className="lg-doc">
        <nav className="lg-tabs" aria-label="Legal pages">
          <a href="/privacy" onClick={go("/privacy")} aria-current={page === "privacy" ? "page" : undefined}>Privacy policy</a>
          <a href="/terms" onClick={go("/terms")} aria-current={page === "terms" ? "page" : undefined}>Terms of use</a>
        </nav>
        <article className="lg-body">{page === "terms" ? <Terms /> : <Privacy />}</article>
        <p className="lg-back"><a href="/" onClick={(e) => { e.preventDefault(); onHome(); }}><Icon name="chevron" size={14} stroke={2.4} /> Back to the overview</a></p>
      </main>
    </div>
  );
}

// Small "Privacy · Terms" links for footers.
export function LegalLinks({ className = "" }) {
  const go = (path) => (e) => { e.preventDefault(); window.history.pushState(null, "", path); window.dispatchEvent(new PopStateEvent("popstate")); };
  return (
    <span className={`lg-links ${className}`}>
      <a href="/privacy" onClick={go("/privacy")}>Privacy policy</a>
      <span aria-hidden="true">·</span>
      <a href="/terms" onClick={go("/terms")}>Terms of use</a>
    </span>
  );
}
