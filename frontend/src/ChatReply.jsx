import React from 'react';
import Markdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

function Heading({children}) {
  return <p className="chat-reply-heading"><strong>{children}</strong></p>;
}

const components = {
  h1: Heading, h2: Heading, h3: Heading, h4: Heading, h5: Heading, h6: Heading,
  a: ({href, children}) => href
    ? <a href={href} target="_blank" rel="noopener noreferrer">{children}</a>
    : <span>{children}</span>,
  table: ({children}) => <div className="chat-table-scroll" tabIndex={0} role="region" aria-label="Answer table"><table>{children}</table></div>,
};

// Display old saved Markdown too. React escapes text; raw HTML is never executed.
export default function ChatReply({text}) {
  return <div className="chat-prose"><Markdown remarkPlugins={[remarkGfm]} components={components} skipHtml>
    {String(text || '').replace(/<br\s*\/?>/gi, ' ')}
  </Markdown></div>;
}
