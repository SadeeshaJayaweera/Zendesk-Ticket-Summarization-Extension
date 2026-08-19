/**
 * Zendesk Ticket Summarizer — Client Application Logic
 *
 * Integrates with the Zendesk Apps Framework (ZAF v2) SDK and interacts
 * with the FastAPI backend service for Gemini & Groq summarization.
 */

document.addEventListener('DOMContentLoaded', () => {
  let client = null;
  let currentTicketId = null;
  let currentTicketData = null;
  let backendUrl = 'http://localhost:8000';
  let selectedStyle = 'standard';
  let isHistoryOpen = false;

  // --- DOM Elements ---
  const statusDot = document.getElementById('status-dot');
  const statusText = document.getElementById('status-text');
  const errorBanner = document.getElementById('error-banner');
  const errorTitle = document.getElementById('error-title');
  const errorMessage = document.getElementById('error-message');
  const errorCloseBtn = document.getElementById('error-close-btn');

  const ticketIdTag = document.getElementById('ticket-id-tag');
  const ticketStatusTag = document.getElementById('ticket-status-tag');
  const ticketSubject = document.getElementById('ticket-subject');
  const ticketRequester = document.getElementById('ticket-requester');
  const ticketPriority = document.getElementById('ticket-priority');

  const btnSummarize = document.getElementById('btn-summarize');
  const btnSummarizeText = document.getElementById('btn-summarize-text');
  const summarizeSpinner = document.getElementById('summarize-spinner');
  const summarizeIcon = document.getElementById('summarize-icon');
  const skeletonContainer = document.getElementById('skeleton-container');
  const summarySection = document.getElementById('summary-section');

  const tabBtnMarkdown = document.getElementById('tab-btn-markdown');
  const tabBtnFormatted = document.getElementById('tab-btn-formatted');
  const tabMarkdown = document.getElementById('tab-markdown');
  const tabFormatted = document.getElementById('tab-formatted');

  const markdownEditor = document.getElementById('markdown-editor');
  const charCount = document.getElementById('char-count');

  const sentimentPill = document.getElementById('sentiment-pill');
  const currentStatusPill = document.getElementById('current-status-pill');
  const summaryExec = document.getElementById('summary-exec');
  const summaryIssue = document.getElementById('summary-issue');
  const timelineList = document.getElementById('timeline-list');
  const commitmentsList = document.getElementById('commitments-list');
  const actionChecklist = document.getElementById('action-checklist');
  const blockActions = document.getElementById('block-actions');
  const blockCommitments = document.getElementById('block-commitments');
  const blockItems = document.getElementById('block-items');

  const btnCopy = document.getElementById('btn-copy');
  const btnInsertComposer = document.getElementById('btn-insert-composer');
  const btnPostDirect = document.getElementById('btn-post-direct');
  const postSpinner = document.getElementById('post-spinner');
  const postIcon = document.getElementById('post-icon');
  const postText = document.getElementById('post-text');

  const historyToggleBtn = document.getElementById('history-toggle-btn');
  const historyContent = document.getElementById('history-content');
  const historyArrow = document.getElementById('history-arrow');
  const historyList = document.getElementById('history-list');
  const historyCount = document.getElementById('history-count');
  const pendingDraftBanner = document.getElementById('pending-draft-banner');

  const toast = document.getElementById('toast');
  const toastIcon = document.getElementById('toast-icon');
  const toastMessage = document.getElementById('toast-message');

  // --- Initialize ZAF SDK or Fallback to Standalone Dev Mode ---
  if (typeof ZAFClient !== 'undefined') {
    client = ZAFClient.init();
    client.on('app.registered', initZafApp);
    client.on('ticket.saved', () => {
      loadTicketHistory();
      checkPendingDraft();
    });
  } else {
    initStandaloneDevMode();
  }

  /**
   * Initialize inside Zendesk Agent Workspace via ZAF
   */
  async function initZafApp() {
    try {
      resizeIframe(360);

      // Read backendUrl parameter from App installation settings
      try {
        const metadata = await client.metadata();
        if (metadata?.settings?.backendUrl) {
          backendUrl = metadata.settings.backendUrl.trim().replace(/\/+$/, '');
        }
      } catch (e) {
        console.warn('Could not read metadata settings:', e);
      }

      // Fetch active ticket metadata from ZAF context
      const zafData = await client.get([
        'ticket.id',
        'ticket.subject',
        'ticket.status',
        'ticket.priority',
        'ticket.requester.name',
      ]);

      currentTicketId = zafData['ticket.id'];
      currentTicketData = {
        id: currentTicketId,
        subject: zafData['ticket.subject'] || 'No Subject',
        status: zafData['ticket.status'] || 'open',
        priority: zafData['ticket.priority'] || 'normal',
        requester: zafData['ticket.requester.name'] || 'Customer',
      };

      updateTicketCardUI(currentTicketData);
      checkBackendHealth();
      loadTicketHistory();
      checkPendingDraft();
    } catch (err) {
      console.error('ZAF initialization error:', err);
      showErrorBanner('Zendesk Integration', 'Could not read ticket context from Zendesk workspace.');
    }
  }

  /**
   * Fallback for opening assets/index.html directly in a web browser
   */
  function initStandaloneDevMode() {
    currentTicketId = 1001;
    currentTicketData = {
      id: currentTicketId,
      subject: 'SSO 403 Forbidden error after corporate password reset',
      status: 'solved',
      priority: 'high',
      requester: 'Alex Rivera',
    };
    updateTicketCardUI(currentTicketData);
    statusText.textContent = 'Dev Preview';
    statusDot.className = 'status-dot online';
    checkBackendHealth();
    loadTicketHistory();
    checkPendingDraft();
  }


  function updateTicketCardUI(data) {
    if (!data) return;
    ticketIdTag.textContent = `#${data.id || 'N/A'}`;
    ticketStatusTag.textContent = data.status || 'open';
    ticketSubject.textContent = data.subject || 'No Subject';
    ticketRequester.textContent = `👤 ${data.requester || 'Customer'}`;
    const p = data.priority || 'normal';
    ticketPriority.textContent = `⚡ ${p.charAt(0).toUpperCase() + p.slice(1)}`;
  }

  /**
   * Check backend service connectivity
   */
  async function checkBackendHealth() {
    try {
      const resp = await fetch(`${backendUrl}/health`, { signal: AbortSignal.timeout(3000) });
      if (resp.ok) {
        statusDot.className = 'status-dot online';
        statusText.textContent = 'Backend Online';
      } else {
        statusDot.className = 'status-dot busy';
        statusText.textContent = 'Backend Issue';
      }
    } catch (e) {
      statusDot.className = 'status-dot';
      statusText.textContent = 'Backend Offline';
    }
  }

  // --- Format Selector Buttons ---
  document.querySelectorAll('.style-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.style-btn').forEach((b) => b.classList.remove('active'));
      btn.classList.add('active');
      selectedStyle = btn.dataset.style;
    });
  });

  // --- Tab Navigation ---
  tabBtnMarkdown.addEventListener('click', () => {
    tabBtnMarkdown.classList.add('active');
    tabBtnFormatted.classList.remove('active');
    tabMarkdown.classList.add('active');
    tabFormatted.classList.remove('active');
    autoAdjustHeight();
  });

  tabBtnFormatted.addEventListener('click', () => {
    tabBtnFormatted.classList.add('active');
    tabBtnMarkdown.classList.remove('active');
    tabFormatted.classList.add('active');
    tabMarkdown.classList.remove('active');
    autoAdjustHeight();
  });

  // --- Live Character Counter ---
  markdownEditor.addEventListener('input', () => {
    const len = markdownEditor.value.length;
    charCount.textContent = `${len} char${len === 1 ? '' : 's'}`;
  });

  // --- Error Banner Dismiss ---
  errorCloseBtn.addEventListener('click', hideErrorBanner);

  function showErrorBanner(title, message) {
    errorTitle.textContent = title;
    errorMessage.textContent = message;
    errorBanner.style.display = 'block';
    autoAdjustHeight();
  }

  function hideErrorBanner() {
    errorBanner.style.display = 'none';
    autoAdjustHeight();
  }

  /**
   * Action: Summarize Ticket
   */
  btnSummarize.addEventListener('click', async () => {
    hideErrorBanner();
    setLoadingState(true);

    try {
      let data = null;

      if (currentTicketId) {
        const resp = await fetch(`${backendUrl}/api/tickets/${currentTicketId}/summarize`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ summary_style: selectedStyle }),
        });

        if (resp.ok) {
          data = await resp.json();
        } else {
          let errorDetail = `Backend HTTP error ${resp.status}`;
          try {
            const errJson = await resp.json();
            errorDetail = errJson.detail || errJson.message || errorDetail;
          } catch (_) {}

          if (resp.status === 401 || resp.status === 403) {
            throw new Error(`Authentication failure: ${errorDetail}`);
          } else if (resp.status === 429) {
            throw new Error(`AI Rate limit reached: ${errorDetail}`);
          } else if (resp.status === 404) {
            throw new Error(`Ticket #${currentTicketId} not found on Zendesk.`);
          } else {
            throw new Error(errorDetail);
          }
        }
      } else {
        throw new Error('No ticket ID available in current context.');
      }

      renderSummary(data);
      showToast('✨ AI Summary generated! Review draft note below.', 'success');
    } catch (err) {
      console.warn('Summarize error:', err);
      // If running standalone with no backend, show simulated mock preview
      if (!client) {
        const fallback = generateMockSummary();
        renderSummary(fallback);
        showToast('ℹ️ Standalone Dev Preview generated.', 'info');
      } else {
        showErrorBanner('Summarization Failed', err.message || 'Could not produce summary.');
        showToast('⚠️ Summarization failed. See details above.', 'error');
      }
    } finally {
      setLoadingState(false);
      autoAdjustHeight();
    }
  });

  /**
   * Render AI structured summary and populate editor
   */
  function renderSummary(data) {
    if (!data) return;
    const summary = data.summary;

    // Visual breakdown
    sentimentPill.textContent = getSentimentBadge(summary.sentiment);
    currentStatusPill.textContent = summary.current_status || 'Open';
    summaryExec.textContent = summary.executive_summary || 'N/A';
    summaryIssue.textContent = summary.customer_issue || 'N/A';

    // Actions list
    timelineList.innerHTML = '';
    if (summary.actions_taken && summary.actions_taken.length > 0) {
      blockActions.style.display = 'flex';
      summary.actions_taken.forEach((act) => {
        const li = document.createElement('li');
        li.textContent = act;
        timelineList.appendChild(li);
      });
    } else {
      blockActions.style.display = 'none';
    }

    // Commitments list
    commitmentsList.innerHTML = '';
    if (summary.commitments && summary.commitments.length > 0) {
      blockCommitments.style.display = 'flex';
      summary.commitments.forEach((c) => {
        const li = document.createElement('li');
        li.textContent = c;
        commitmentsList.appendChild(li);
      });
    } else {
      blockCommitments.style.display = 'none';
    }

    // Action checklist
    actionChecklist.innerHTML = '';
    if (summary.action_items && summary.action_items.length > 0) {
      blockItems.style.display = 'flex';
      summary.action_items.forEach((item) => {
        const li = document.createElement('li');
        const checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        const span = document.createElement('span');
        span.textContent = item;
        li.appendChild(checkbox);
        li.appendChild(span);
        actionChecklist.appendChild(li);
      });
    } else {
      blockItems.style.display = 'none';
    }

    // Populate editable markdown textarea
    const noteText = data.markdown_note || '';
    markdownEditor.value = noteText;
    charCount.textContent = `${noteText.length} chars`;

    // Show output section
    summarySection.style.display = 'flex';
  }

  function getSentimentBadge(sentiment) {
    const s = (sentiment || 'neutral').toLowerCase();
    switch (s) {
      case 'positive': return '🟢 Positive';
      case 'frustrated': return '🟠 Frustrated';
      case 'urgent': return '🔴 Urgent';
      default: return '⚪ Neutral';
    }
  }

  /**
   * Action: Copy Markdown Note
   */
  btnCopy.addEventListener('click', async () => {
    const text = markdownEditor.value;
    if (!text) return;

    try {
      await navigator.clipboard.writeText(text);
      showToast('📋 Copied Markdown note to clipboard!', 'success');
    } catch (e) {
      markdownEditor.select();
      document.execCommand('copy');
      showToast('📋 Copied to clipboard!', 'success');
    }
  });

  /**
   * Action: Insert into Zendesk Internal Note Composer (ZAF SDK)
   */
  btnInsertComposer.addEventListener('click', async () => {
    const noteText = markdownEditor.value;
    if (!noteText) {
      showToast('⚠️ No note content to insert.', 'warning');
      return;
    }

    if (client) {
      try {
        await client.set('ticket.comment.type', 'internalNote');
        await client.set('ticket.comment.text', noteText);
        showToast('📝 Inserted into Zendesk Internal Note composer!', 'success');
      } catch (err) {
        console.error('Error inserting into composer:', err);
        showToast('⚠️ Could not insert into composer automatically.', 'error');
      }
    } else {
      showToast('📝 (Dev Mode) Inserted note into composer.', 'info');
    }
  });

  /**
   * Action: Direct API Post Note (calls /api/tickets/{id}/notes with public=false)
   */
  btnPostDirect.addEventListener('click', async () => {
    const noteText = markdownEditor.value;
    if (!noteText) {
      showToast('⚠️ Note content is empty.', 'warning');
      return;
    }
    if (!currentTicketId) {
      showToast('⚠️ No active ticket ID found.', 'error');
      return;
    }

    hideErrorBanner();
    setPostingState(true);

    try {
      const resp = await fetch(`${backendUrl}/api/tickets/${currentTicketId}/notes`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ body: noteText, public: false }),
      });

      if (resp.ok) {
        showToast('🚀 Internal note posted to Zendesk ticket!', 'success');
        pendingDraftBanner.style.display = 'none';
        loadTicketHistory();
      } else {

        let errorDetail = `Backend HTTP ${resp.status}`;
        try {
          const errJson = await resp.json();
          errorDetail = errJson.detail || errJson.message || errorDetail;
        } catch (_) {}
        throw new Error(errorDetail);
      }
    } catch (err) {
      console.warn('Post note error:', err);
      if (!client) {
        showToast('🚀 (Dev Mode) Note posted successfully!', 'success');
      } else {
        showErrorBanner('Post Failed', err.message || 'Could not post note to ticket.');
        showToast('⚠️ Post failed. See details above.', 'error');
      }
    } finally {
      setPostingState(false);
      autoAdjustHeight();
    }
  });

  /**
   * History Accordion Toggle & Fetch
   */
  historyToggleBtn.addEventListener('click', () => {
    isHistoryOpen = !isHistoryOpen;
    historyContent.style.display = isHistoryOpen ? 'block' : 'none';
    historyArrow.classList.toggle('open', isHistoryOpen);
    if (isHistoryOpen) {
      loadTicketHistory();
    }
    autoAdjustHeight();
  });

  async function loadTicketHistory() {
    if (!currentTicketId) return;

    try {
      const resp = await fetch(`${backendUrl}/api/tickets/${currentTicketId}/history`, {
        signal: AbortSignal.timeout(4000),
      });

      if (resp.ok) {
        const data = await resp.json();
        renderHistoryList(data.summaries || []);
      } else {
        renderHistoryList([]);
      }
    } catch (err) {
      renderHistoryList([]);
    }
  }

  function renderHistoryList(summaries) {
    historyCount.textContent = summaries.length;
    historyList.innerHTML = '';

    if (!summaries || summaries.length === 0) {
      const p = document.createElement('p');
      p.className = 'history-empty';
      p.textContent = 'No past AI summaries found on this ticket.';
      historyList.appendChild(p);
      return;
    }

    summaries.forEach((item, idx) => {
      const card = document.createElement('div');
      card.className = 'history-card';

      const header = document.createElement('div');
      header.className = 'history-card-header';
      const timeStr = item.created_at ? new Date(item.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : `Note #${idx + 1}`;
      header.innerHTML = `<span>🕒 ${timeStr}</span><span>${item.is_internal ? '🔒 Internal' : 'Public'}</span>`;

      const body = document.createElement('div');
      body.className = 'history-card-body';
      body.textContent = item.body;

      const actions = document.createElement('div');
      actions.className = 'history-card-actions';

      const useBtn = document.createElement('button');
      useBtn.type = 'button';
      useBtn.className = 'history-use-btn';
      useBtn.textContent = 'Load into Editor';
      useBtn.addEventListener('click', () => {
        markdownEditor.value = item.body;
        charCount.textContent = `${item.body.length} chars`;
        tabBtnMarkdown.click();
        showToast('📋 Past summary loaded into editor!', 'info');
      });

      actions.appendChild(useBtn);
      card.appendChild(header);
      card.appendChild(body);
      card.appendChild(actions);
      autoAdjustHeight();
  }

  /**
   * Check for automated pre-drafted summary from Zendesk solve trigger
   */
  async function checkPendingDraft() {
    if (!currentTicketId) return;

    try {
      const resp = await fetch(`${backendUrl}/api/tickets/${currentTicketId}/pending-draft`, {
        signal: AbortSignal.timeout(3500),
      });

      if (resp.ok) {
        const data = await resp.json();
        if (data.has_pending_draft && data.draft) {
          pendingDraftBanner.style.display = 'block';
          renderSummary(data.draft);
          showToast('⚡ Pre-draft summary ready for review!', 'success');
          autoAdjustHeight();
        } else {
          pendingDraftBanner.style.display = 'none';
        }
      }
    } catch (e) {
      console.log('No pending draft found or service offline');
    }
  }


  /**
   * Helper: Loading and Posting Button UI States
   */
  function setLoadingState(isLoading) {
    btnSummarize.disabled = isLoading;
    if (isLoading) {
      summarizeSpinner.style.display = 'inline-block';
      summarizeIcon.style.display = 'none';
      btnSummarizeText.textContent = 'Analyzing Ticket...';
      skeletonContainer.style.display = 'flex';
      summarySection.style.display = 'none';
    } else {
      summarizeSpinner.style.display = 'none';
      summarizeIcon.style.display = 'inline';
      btnSummarizeText.textContent = 'Re-summarize Ticket';
      skeletonContainer.style.display = 'none';
    }
  }

  function setPostingState(isPosting) {
    btnPostDirect.disabled = isPosting;
    if (isPosting) {
      postSpinner.style.display = 'inline-block';
      postIcon.style.display = 'none';
      postText.textContent = 'Posting Note...';
    } else {
      postSpinner.style.display = 'none';
      postIcon.style.display = 'inline';
      postText.textContent = 'Post as Internal Note';
    }
  }

  function showToast(message, type = 'info') {
    toastMessage.textContent = message;
    if (type === 'success') toastIcon.textContent = '✅';
    else if (type === 'error') toastIcon.textContent = '⚠️';
    else if (type === 'warning') toastIcon.textContent = '⏳';
    else toastIcon.textContent = 'ℹ️';

    toast.classList.add('show');
    setTimeout(() => {
      toast.classList.remove('show');
    }, 3200);
  }

  function resizeIframe(height) {
    if (client && typeof client.invoke === 'function') {
      client.invoke('resize', { width: '100%', height: `${height}px` });
    }
  }

  function autoAdjustHeight() {
    if (!client) return;
    const bodyHeight = Math.min(Math.max(document.body.scrollHeight + 20, 360), 750);
    resizeIframe(bodyHeight);
  }

  function generateMockSummary() {
    return {
      ticket_id: currentTicketId,
      subject: currentTicketData?.subject || 'Support Ticket',
      model_used: 'gemini-1.5-flash',
      summary: {
        executive_summary: 'Customer blocked by 403 Forbidden error during SSO login following a corporate password reset.',
        customer_issue: 'SAML assertion token expired or mismatch in active directory group mappings.',
        actions_taken: [
          'Customer attempted login across Chrome and Safari.',
          'Agent verified user identity and reviewed authentication audit logs.',
          'Identified revoked token certificate.',
        ],
        current_status: 'Awaiting customer re-authentication after certificate refresh',
        commitments: [
          'Follow up with customer within 2 hours if no reply received',
          'Send direct recovery link if SSO continues failing',
        ],
        action_items: [
          'Verify user session in Okta log dashboard',
          'Close ticket once customer confirms portal access is restored',
        ],
        sentiment: 'frustrated',
      },
      markdown_note: `### 🤖 AI Ticket Summary
**Executive Summary:** Customer blocked by 403 Forbidden error during SSO login following a corporate password reset.

**Customer Issue:** SAML assertion token expired or mismatch in active directory group mappings.

**Current Status:** Awaiting customer re-authentication | **Sentiment:** 🟠 Frustrated

**Actions Taken / Troubleshooting:**
- Customer attempted login across Chrome and Safari.
- Agent verified user identity and reviewed authentication audit logs.
- Identified revoked token certificate.

**Commitments / Promised Follow-ups:**
- ⏳ Follow up with customer within 2 hours if no reply received
- ⏳ Send direct recovery link if SSO continues failing

**Next Steps / Action Items:**
- [ ] Verify user session in Okta log dashboard
- [ ] Close ticket once customer confirms portal access is restored

*Generated automatically by Support AI Assistant*`,
    };
  }
});
