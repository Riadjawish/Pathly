"use client";

import { FormEvent, useMemo, useState } from "react";
import Link from "next/link";
import {
  ArrowLeft, Check, ChevronDown, FileQuestion,
  FileUp, Mail, Search, Send, Sparkles, UserRound,
  Wrench,
} from "lucide-react";
import { AppMobileNav, AppSidebar } from "../_components/app-sidebar";

const faqs = [
  ["How do I upload course materials?", "Open Subjects, choose a course workspace, then add files to Course PDFs, Notes & Slides, Past Exams or Practice Problems."],
  ["How does PATHLY create my mastery map?", "PATHLY reads your uploaded materials, identifies topics and prerequisites, then organizes lessons from foundations through exam readiness."],
  ["Why is a level locked?", "Levels unlock in order. Complete the current lesson and its quiz to open the next step in your journey."],
  ["Can I edit or delete a subject?", "Yes. Open the Subjects page and use the edit or delete controls on the subject card."],
  ["Are my uploaded files private?", "Your course materials are intended to remain private to your account and are only used to build your learning experience."],
];

export default function SupportPage() {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(0);
  const [sent, setSent] = useState(false);
  const filtered = useMemo(() => faqs.filter(([question]) => question.toLowerCase().includes(query.toLowerCase())), [query]);
  function sendMessage(event: FormEvent) { event.preventDefault(); setSent(true); }
  return <main className="settings-page support-page"><AppSidebar active="support" />
    <section className="settings-content"><header className="page-title"><Link href="/"><ArrowLeft /></Link><div><span>PATHLY SUPPORT</span><h1>How can we help?</h1><p>Search for an answer or contact the support team.</p></div></header>
      <section className="support-hero"><Sparkles /><h2>Find answers in seconds</h2><label><Search /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search uploads, maps, subjects, account..." /></label></section>
      <section className="support-shortcuts"><article><FileUp /><h3>Uploading files</h3><p>Accepted formats and organization</p></article><article><Wrench /><h3>Troubleshooting</h3><p>Fix common app problems</p></article><article><FileQuestion /><h3>AI & mastery maps</h3><p>How your path is generated</p></article><article><UserRound /><h3>Account & privacy</h3><p>Profile and data controls</p></article></section>
      <div className="support-grid"><section className="faq-card"><span>FREQUENTLY ASKED QUESTIONS</span><h2>Popular answers</h2><div className="faq-list">{filtered.map(([question, answer], index) => <article className={open === index ? "open" : ""} key={question}><button onClick={() => setOpen(open === index ? -1 : index)}><b>{question}</b><ChevronDown /></button>{open === index && <p>{answer}</p>}</article>)}{filtered.length === 0 && <div className="no-answer"><Search /><p>No matching answers. Send us a message instead.</p></div>}</div></section>
        <form className="contact-card" onSubmit={sendMessage}><span>CONTACT SUPPORT</span><h2>Send us a message</h2><p>Tell us what happened and we’ll help you solve it.</p><label>Your email<div><Mail /><input required type="email" placeholder="you@example.com" /></div></label><label>What do you need help with?<select><option>Uploading materials</option><option>Mastery map</option><option>Account</option><option>Technical problem</option><option>Other</option></select></label><label>Message<textarea required placeholder="Describe the problem..." /></label><button>{sent ? <><Check /> Message sent</> : <><Send /> Send message</>}</button></form></div>
    </section><AppMobileNav active="support" /></main>;
}
