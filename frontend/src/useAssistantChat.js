import {useEffect, useRef, useState} from 'react';
import {api} from './api';

const noop = () => {};
const finished = new Set(['succeeded', 'failed', 'cancelled', 'unavailable', 'clarification']);

export default function useAssistantChat({siteId, conversationId, user, restore, onCreated = noop}) {
  const [config, setConfig] = useState(null), [c, setC] = useState(null);
  const [text, setText] = useState(''), [error, setError] = useState('');
  const [busy, setBusy] = useState(false), [attachment, setAttachment] = useState(null);
  const current = useRef(null), generation = useRef(0), sequence = useRef(0);
  const seen = useRef(new Set()), pendingSend = useRef(null), inFlight = useRef(false);
  const storageKey = 'jg-conversation-' + user.email + '-' + (siteId || 'organization');
  const valid = epoch => generation.current === epoch;

  async function load(id = current.current, epoch = generation.current) {
    if (!id || !valid(epoch)) return;
    const request = ++sequence.current;
    try {
      const data = await api('/assistant/conversations/' + id);
      if (!valid(epoch) || request !== sequence.current || String(current.current) !== String(id)) return;
      setC(data);
      for (const job of data.workflows) {
        if (job.status === 'succeeded' && !seen.current.has(job.id)) {
          seen.current.add(job.id);
          window.dispatchEvent(new Event('jg-data-changed'));
        }
      }
    } catch (e) {
      if (valid(epoch) && request === sequence.current) setError(e.message);
    }
  }

  useEffect(() => {
    const epoch = ++generation.current;
    const id = conversationId || (restore ? sessionStorage.getItem(storageKey) : null);
    current.current = id;
    setC(null); setText(''); setAttachment(null); setError(''); setBusy(false);
    inFlight.current = false; pendingSend.current = null;
    if (id) load(id, epoch);
    // Retire all outstanding loads and sends when changing chats or closing the drawer.
    return () => {generation.current++};
  }, [conversationId, storageKey, restore]);

  useEffect(() => {
    let active = true;
    api('/assistant/config').then(value => {if (active) setConfig(value)}).catch(e => {if (active) setError(e.message)});
    return () => {active = false};
  }, []);

  const hasWork = !!c?.workflows.some(job => !finished.has(job.status));
  useEffect(() => {
    if (!c?.id || !hasWork) return;
    let active = true, timer;
    const epoch = generation.current, id = c.id;
    async function poll() {
      await load(id, epoch);
      if (active && valid(epoch)) timer = setTimeout(poll, 2000);
    }
    timer = setTimeout(poll, 2000);
    return () => {active = false; clearTimeout(timer)};
  }, [c?.id, hasWork]);

  async function ensure(epoch) {
    if (current.current) return current.current;
    const data = await api('/assistant/conversations', {method: 'POST', body: {site_id: siteId}});
    if (!valid(epoch)) return null;
    current.current = data.id;
    if (restore) sessionStorage.setItem(storageKey, data.id);
    return data.id;
  }

  async function send(e) {
    e.preventDefault();
    if (!text.trim() || inFlight.current) return;
    const epoch = generation.current, message = text;
    inFlight.current = true; setBusy(true); setError('');
    try {
      const id = await ensure(epoch);
      if (!id || !valid(epoch)) return;
      const pending = c?.workflows.find(job => job.status === 'clarification');
      if (pending) {
        await api('/assistant/workflows/' + pending.id + '/clarify', {method: 'POST', body: {text: message}});
      } else {
        // Retrying after a lost response must not execute the same task twice.
        if (!pendingSend.current || pendingSend.current.id !== id || pendingSend.current.text !== message) {
          pendingSend.current = {id, text: message, request_key: crypto.randomUUID()};
        }
        const {text: bodyText, request_key} = pendingSend.current;
        await api('/assistant/conversations/' + id + '/messages', {method: 'POST', body: {text: bodyText, request_key}});
      }
      if (!valid(epoch)) return;
      pendingSend.current = null;
      setText(''); setAttachment(null);
      await load(id, epoch);
      if (valid(epoch)) onCreated(id);
    } catch (e) {
      if (valid(epoch)) setError(e.message);
    } finally {
      if (valid(epoch)) {inFlight.current = false; setBusy(false)}
    }
  }

  async function attach(e) {
    const input = e.target, uploaded = input.files[0];
    if (!uploaded || inFlight.current) return;
    const epoch = generation.current;
    inFlight.current = true; setBusy(true); setError('');
    try {
      const id = await ensure(epoch);
      if (!id || !valid(epoch)) return;
      const body = new FormData(); body.append('file', uploaded);
      const added = await api('/assistant/conversations/' + id + '/attachments', {method: 'POST', body});
      if (!valid(epoch)) return;
      setAttachment(added); setText(value => value + ' Use attachment #' + added.id + '.');
      await load(id, epoch);
    } catch (e) {
      if (valid(epoch)) setError(e.message);
    } finally {
      input.value = '';
      if (valid(epoch)) {inFlight.current = false; setBusy(false)}
    }
  }

  function fresh() {
    generation.current++;
    current.current = null; pendingSend.current = null; inFlight.current = false;
    setC(null); setText(''); setAttachment(null); setError(''); setBusy(false);
    if (restore) sessionStorage.removeItem(storageKey);
    // Old chats and any already-submitted tasks remain in history.
    onCreated(null);
  }

  return {config, c, text, setText, error, busy, attachment, load, send, attach, fresh};
}
