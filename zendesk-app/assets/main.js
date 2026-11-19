/**
 * Zendesk Ticket Summarizer & Intelligence Platform — Client Application Logic
 *
 * Integrates with the Zendesk Apps Framework (ZAF v2) SDK and interacts
 * with the FastAPI backend service for Multi-Provider AI Support Intelligence.
 */

document.addEventListener('DOMContentLoaded', () => {
  let client = null;
  let currentTicketId = null;
  let currentTicketData = null;
  let backendUrl = 'http://localhost:8000';
  let selectedStyle = 'standard';
  let isHistoryOpen = false;
  let pendingConfirmAction = null;

  // --- DOM Elements: Status & Header ---
  const statusDot = document.getElementById('status-dot');
  const statusText = document.getElementById('status-text');
  const errorBanner = document.getElementById('error-banner');
  const errorTitle = document.getElementById('error-title');
  const errorMessage = document.getElementById('error-message');
  const errorCloseBtn = document.getElementById('error-close-btn');

  // Ticket Context Card
  const ticketIdTag = document.getElementById('ticket-id-tag');
  const ticketStatusTag = document.getElementById('ticket-status-tag');
  const ticketSubject = document.getElementById('ticket-subject');
  const ticketRequester = document.getElementById('ticket-requester');
  const ticketPriority = document.getElementById('ticket-priority');

  // Navigation Tabs
  const navTabs = document.querySelectorAll('.nav-tab');
  const tabViews = document.querySelectorAll('.tab-view');

  // Common Loading Indicator
  const skeletonContainer = document.getElementById('skeleton-container');

  // --- View 1: Summary Elements ---
  const summaryStyleSelect = document.getElementById('summary-style-select');
  const btnSummarize = document.getElementById('btn-summarize');
  const btnSummarizeText = document.getElementById('btn-summarize-text');
  const summarizeSpinner = document.getElementById('summarize-spinner');
  const summarizeIcon = document.getElementById('summarize-icon');
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

  // --- View 2: Troubleshoot Elements ---
  const btnTroubleshoot = document.getElementById('btn-troubleshoot');
  const troubleshootResults = document.getElementById('troubleshoot-results');
  const troubleshootSteps = document.getElementById('troubleshoot-steps');

  // --- View 3: Reply Elements ---
  const replyToneSelect = document.getElementById('reply-tone-select');
  const btnDraftReply = document.getElementById('btn-draft-reply');
  const replyDraftResults = document.getElementById('reply-draft-results');
  const replyDraftTextarea = document.getElementById('reply-draft-textarea');
  const btnCopyReply = document.getElementById('btn-copy-reply');
  const btnInsertReply = document.getElementById('btn-insert-reply');

  // --- View 4: Triage Elements ---
  const btnClassify = document.getElementById('btn-classify');
  const triageResults = document.getElementById('triage-results');
  const triageCategory = document.getElementById('triage-category');
  const triageSubcategory = document.getElementById('triage-subcategory');
  const triagePriority = document.getElementById('triage-priority');
  const triageComplexity = document.getElementById('triage-complexity');
  const triageDepartment = document.getElementById('triage-department');
  const triageConfidence = document.getElementById('triage-confidence');
  const triageRationale = document.getElementById('triage-rationale');

  // --- View 5: Radar Elements ---
  const btnAnalyzeSentiment = document.getElementById('btn-analyze-sentiment');
  const radarResults = document.getElementById('radar-results');
  const radarSentiment = document.getElementById('radar-sentiment');
  const radarFrustration = document.getElementById('radar-frustration');
  const radarChurn = document.getElementById('radar-churn');
  const radarConcerns = document.getElementById('radar-concerns');
  const radarExplanation = document.getElementById('radar-explanation');

  // --- View 6: Escalation Elements ---
  const btnGenEscalation = document.getElementById('btn-gen-escalation');
  const escalationResults = document.getElementById('escalation-results');
  const escalationTextarea = document.getElementById('escalation-textarea');
  const btnCopyEscalation = document.getElementById('btn-copy-escalation');

  // --- View 7: Handover Elements ---
  const btnGenHandover = document.getElementById('btn-gen-handover');
  const handoverResults = document.getElementById('handover-results');
  const handoverTextarea = document.getElementById('handover-textarea');
  const btnCopyHandover = document.getElementById('btn-copy-handover');
  const btnPostHandover = document.getElementById('btn-post-handover');

  // --- View 8: Knowledge Elements ---
  const btnFetchKb = document.getElementById('btn-fetch-kb');
  const kbResults = document.getElementById('kb-results');
  const kbArticleList = document.getElementById('kb-article-list');

  // --- View 9: Similar Elements ---
  const btnFetchSimilar = document.getElementById('btn-fetch-similar');
  const similarResults = document.getElementById('similar-results');
  const similarTicketList = document.getElementById('similar-ticket-list');

  // --- Confirmation Modal & Toast ---
  const confirmModal = document.getElementById('confirm-modal');
  const modalTitle = document.getElementById('modal-title');
  const modalDesc = document.getElementById('modal-desc');
  const btnModalCancel = document.getElementById('btn-modal-cancel');
  const btnModalConfirm = document.getElementById('btn-modal-confirm');

  const toast = document.getElementById('toast');
  const toastIcon = document.getElementById('toast-icon');
  const toastMessage = document.getElementById('toast-message');

  // =========================================================================
  // Initialisation (ZAF SDK or Standalone Dev Preview)
  // =========================================================================
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

  async function initZafApp() {
    try {
      resizeIframe(420);

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

  async function checkBackendHealth() {
    try {
      const resp = await fetch(`${backendUrl}/health`, { signal: AbortSignal.timeout(3000) });
      if (resp.ok) {
        statusDot.className = 'status-dot online';
        statusText.textContent = 'Ready';
      } else {
        statusDot.className = 'status-dot busy';
        statusText.textContent = 'Backend Issue';
      }
    } catch (e) {
      statusDot.className = 'status-dot';
      statusText.textContent = 'Backend Offline';
    }
  }

  // =========================================================================
  // Navigation Tabs Switching (9 Views)
  // =========================================================================
  navTabs.forEach((tab) => {
    tab.addEventListener('click', () => {
      const targetViewId = tab.dataset.view;

      navTabs.forEach((t) => t.classList.remove('active'));
      tab.classList.add('active');

      tabViews.forEach((view) => {
        if (view.id === targetViewId) {
          view.style.display = 'block';
          view.classList.add('active');
        } else {
          view.style.display = 'none';
          view.classList.remove('active');
        }
      });

      autoAdjustHeight();
    });
  });

  // =========================================================================
  // VIEW 1: Summary & Notes Logic
  // =========================================================================
  if (summaryStyleSelect) {
    summaryStyleSelect.addEventListener('change', (e) => {
      selectedStyle = e.target.value;
    });
  }

  // Support legacy format buttons if present in DOM
  document.querySelectorAll('.style-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.style-btn').forEach((b) => b.classList.remove('active'));
      btn.classList.add('active');
      selectedStyle = btn.dataset.style;
      if (summaryStyleSelect) summaryStyleSelect.value = selectedStyle;
    });
  });

  tabBtnMarkdown?.addEventListener('click', () => {
    tabBtnMarkdown.classList.add('active');
    tabBtnFormatted.classList.remove('active');
    tabMarkdown.classList.add('active');
    tabFormatted.classList.remove('active');
    autoAdjustHeight();
  });

  tabBtnFormatted?.addEventListener('click', () => {
    tabBtnFormatted.classList.add('active');
    tabBtnMarkdown.classList.remove('active');
    tabFormatted.classList.add('active');
    tabMarkdown.classList.remove('active');
    autoAdjustHeight();
  });

  markdownEditor?.addEventListener('input', () => {
    const len = markdownEditor.value.length;
    charCount.textContent = `${len} char${len === 1 ? '' : 's'}`;
  });

  btnSummarize?.addEventListener('click', async () => {
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
          throw new Error(errorDetail);
        }
      } else {
        throw new Error('No ticket ID available in current context.');
      }

      renderSummary(data);
      showToast('✨ AI Summary generated! Review draft note below.', 'success');
    } catch (err) {
      console.warn('Summarize error:', err);
      if (!client) {
        const fallback = generateMockSummary();
        renderSummary(fallback);
        showToast('ℹ️ Standalone Dev Preview generated.', 'info');
      } else {
        showErrorBanner('Summarization Failed', err.message || 'Could not produce summary.');
        showToast('⚠️ Summarization failed.', 'error');
      }
    } finally {
      setLoadingState(false);
      autoAdjustHeight();
    }
  });

  function renderSummary(data) {
    if (!data) return;
    const summary = data.summary;

    if (sentimentPill) sentimentPill.textContent = getSentimentBadge(summary.sentiment);
    if (currentStatusPill) currentStatusPill.textContent = summary.current_status || 'Open';
    if (summaryExec) summaryExec.textContent = summary.executive_summary || 'N/A';
    if (summaryIssue) summaryIssue.textContent = summary.customer_issue || 'N/A';

    if (timelineList && blockActions) {
      timelineList.innerHTML = '';
      if (summary.actions_taken && summary.actions_taken.length > 0) {
        blockActions.style.display = 'block';
        summary.actions_taken.forEach((act) => {
          const li = document.createElement('li');
          li.textContent = act;
          timelineList.appendChild(li);
        });
      } else {
        blockActions.style.display = 'none';
      }
    }

    if (commitmentsList && blockCommitments) {
      commitmentsList.innerHTML = '';
      if (summary.commitments && summary.commitments.length > 0) {
        blockCommitments.style.display = 'block';
        summary.commitments.forEach((c) => {
          const li = document.createElement('li');
          li.textContent = c;
          commitmentsList.appendChild(li);
        });
      } else {
        blockCommitments.style.display = 'none';
      }
    }

    if (actionChecklist && blockItems) {
      actionChecklist.innerHTML = '';
      if (summary.action_items && summary.action_items.length > 0) {
        blockItems.style.display = 'block';
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
    }

    const noteText = data.markdown_note || '';
    if (markdownEditor) {
      markdownEditor.value = noteText;
      charCount.textContent = `${noteText.length} chars`;
    }

    if (summarySection) summarySection.style.display = 'flex';
  }

  function getSentimentBadge(sentiment) {
    const s = (sentiment || 'neutral').toLowerCase();
    switch (s) {
      case 'positive': return '🟢 Positive';
      case 'frustrated': return '🟠 Frustrated';
      case 'urgent': return '🔴 Urgent';
      case 'negative': return '🔴 Negative';
      default: return '⚪ Neutral';
    }
  }

  btnCopy?.addEventListener('click', async () => {
    const text = markdownEditor.value;
    if (!text) return;
    await copyText(text);
    showToast('📋 Copied Markdown note to clipboard!', 'success');
  });

  btnInsertComposer?.addEventListener('click', async () => {
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

  btnPostDirect?.addEventListener('click', () => {
    const noteText = markdownEditor.value;
    if (!noteText) {
      showToast('⚠️ Note content is empty.', 'warning');
      return;
    }
    openConfirmModal(
      'Confirm Internal Note Publication',
      `Post this AI Summary as an official internal note on ticket #${currentTicketId}?`,
      () => executePostNote(noteText)
    );
  });

  async function executePostNote(noteText) {
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
        if (pendingDraftBanner) pendingDraftBanner.style.display = 'none';
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
        showToast('⚠️ Post failed.', 'error');
      }
    } finally {
      setPostingState(false);
      autoAdjustHeight();
    }
  }

  // Past Summaries Accordion
  historyToggleBtn?.addEventListener('click', () => {
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
    if (!historyCount || !historyList) return;
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
      historyList.appendChild(card);
    });
    autoAdjustHeight();
  }

  async function checkPendingDraft() {
    if (!currentTicketId) return;

    try {
      const resp = await fetch(`${backendUrl}/api/tickets/${currentTicketId}/pending-draft`, {
        signal: AbortSignal.timeout(3500),
      });

      if (resp.ok) {
        const data = await resp.json();
        if (data.has_pending_draft && data.draft) {
          if (pendingDraftBanner) pendingDraftBanner.style.display = 'block';
          renderSummary(data.draft);
          showToast('⚡ Pre-draft summary ready for review!', 'success');
          autoAdjustHeight();
        } else {
          if (pendingDraftBanner) pendingDraftBanner.style.display = 'none';
        }
      }
    } catch (e) {
      console.log('No pending draft found or service offline');
    }
  }

  // =========================================================================
  // VIEW 2: AI Troubleshooting Assistant
  // =========================================================================
  btnTroubleshoot?.addEventListener('click', async () => {
    hideErrorBanner();
    btnTroubleshoot.disabled = true;
    btnTroubleshoot.innerHTML = '<span class="btn-spinner"></span> Diagnosing...';

    try {
      const resp = await fetch(`${backendUrl}/api/tickets/${currentTicketId}/troubleshoot`, {
        method: 'POST',
      });

      let data;
      if (resp.ok) {
        data = await resp.json();
      } else {
        throw new Error(`Troubleshooting error: ${resp.statusText}`);
      }

      renderTroubleshootResults(data);
      showToast('🔍 Technical investigation steps ready!', 'success');
    } catch (err) {
      console.warn('Troubleshoot error:', err);
      if (!client) {
        renderMockTroubleshoot();
        showToast('ℹ️ Standalone Dev Preview generated.', 'info');
      } else {
        showErrorBanner('Troubleshoot Failed', err.message || 'Diagnostic failed.');
      }
    } finally {
      btnTroubleshoot.disabled = false;
      btnTroubleshoot.innerHTML = '<span class="btn-icon">🔍</span> Generate Diagnostic Workflow';
      autoAdjustHeight();
    }
  });

  function renderTroubleshootResults(data) {
    troubleshootSteps.innerHTML = '';
    const suggestions = data.suggestions || [];

    if (suggestions.length === 0) {
      troubleshootSteps.innerHTML = '<p class="history-empty">No troubleshooting steps generated.</p>';
    } else {
      suggestions.forEach((step, idx) => {
        const card = document.createElement('div');
        card.className = 'step-card';
        card.innerHTML = `
          <div class="step-header">
            <strong>Step ${idx + 1}: ${escapeHtml(step.problem_identified)}</strong>
          </div>
          <div class="step-body">
            <p><strong>Evidence:</strong> ${escapeHtml(step.supporting_evidence || 'N/A')}</p>
            <p><strong>Recommended Action:</strong> ${escapeHtml(step.recommended_investigation)}</p>
            <p><strong>Expected Result:</strong> ${escapeHtml(step.expected_result)}</p>
            ${step.alternative_investigation ? `<p><strong>Alternative:</strong> ${escapeHtml(step.alternative_investigation)}</p>` : ''}
            ${step.escalation_criteria ? `<p class="step-escalate"><strong>Escalate if:</strong> ${escapeHtml(step.escalation_criteria)}</p>` : ''}
          </div>
        `;
        troubleshootSteps.appendChild(card);
      });
    }

    troubleshootResults.style.display = 'block';
  }

  function renderMockTroubleshoot() {
    renderTroubleshootResults({
      suggestions: [
        {
          problem_identified: 'SAML Assertion Expired / Clock Skew',
          supporting_evidence: 'HTTP 403 Forbidden on /saml/sso callback endpoint',
          recommended_investigation: 'Verify user token validity and IdP server timestamp sync in Okta dashboard.',
          expected_result: 'Token validation passes with status ACTIVE.',
          alternative_investigation: 'Generate temporary single-use bypass auth link for user.',
          escalation_criteria: 'Escalate to Tier 3 Identity team if IdP certificate has expired.'
        }
      ]
    });
  }

  // =========================================================================
  // VIEW 3: AI Reply Drafting
  // =========================================================================
  btnDraftReply?.addEventListener('click', async () => {
    hideErrorBanner();
    btnDraftReply.disabled = true;
    btnDraftReply.innerHTML = '<span class="btn-spinner"></span> Drafting Reply...';
    const tone = replyToneSelect?.value || 'professional';

    try {
      const resp = await fetch(`${backendUrl}/api/tickets/${currentTicketId}/draft-reply`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tone }),
      });

      let data;
      if (resp.ok) {
        data = await resp.json();
      } else {
        throw new Error(`Reply drafting error: ${resp.statusText}`);
      }

      replyDraftTextarea.value = data.draft_reply || '';
      replyDraftResults.style.display = 'block';
      showToast('✉️ Reply draft prepared! Review before sending.', 'success');
    } catch (err) {
      console.warn('Reply drafting error:', err);
      if (!client) {
        replyDraftTextarea.value = `Hello Alex,\n\nThank you for reaching out to us. I understand you are experiencing a 403 Forbidden error after resetting your corporate password.\n\nWe have refreshed your authentication certificate and re-synced your group permissions. Please clear your browser cache or open a private window and try signing in again.\n\nLet me know if you run into any further issues!\n\nBest regards,\nCustomer Support Team`;
        replyDraftResults.style.display = 'block';
        showToast('ℹ️ Standalone Dev Preview generated.', 'info');
      } else {
        showErrorBanner('Draft Failed', err.message || 'Could not draft reply.');
      }
    } finally {
      btnDraftReply.disabled = false;
      btnDraftReply.innerHTML = '<span class="btn-icon">✉️</span> Draft Customer Reply';
      autoAdjustHeight();
    }
  });

  btnCopyReply?.addEventListener('click', async () => {
    const text = replyDraftTextarea.value;
    if (!text) return;
    await copyText(text);
    showToast('📋 Copied reply draft to clipboard!', 'success');
  });

  btnInsertReply?.addEventListener('click', async () => {
    const text = replyDraftTextarea.value;
    if (!text) return;
    if (client) {
      try {
        await client.set('ticket.comment.type', 'publicReply');
        await client.set('ticket.comment.text', text);
        showToast('📝 Inserted into Public Reply composer! Please review before sending.', 'success');
      } catch (err) {
        showToast('⚠️ Could not insert reply automatically.', 'error');
      }
    } else {
      showToast('📝 (Dev Mode) Inserted draft into public reply composer.', 'info');
    }
  });

  // =========================================================================
  // VIEW 4: Triage & Classification
  // =========================================================================
  btnClassify?.addEventListener('click', async () => {
    hideErrorBanner();
    btnClassify.disabled = true;
    btnClassify.innerHTML = '<span class="btn-spinner"></span> Classifying...';

    try {
      const resp = await fetch(`${backendUrl}/api/tickets/${currentTicketId}/classify`, {
        method: 'POST',
      });

      let data;
      if (resp.ok) {
        data = await resp.json();
      } else {
        throw new Error(`Classification error: ${resp.statusText}`);
      }

      renderClassification(data);
      showToast('🏷️ Ticket classification completed!', 'success');
    } catch (err) {
      console.warn('Classify error:', err);
      if (!client) {
        renderClassification({
          category: 'Authentication',
          subcategory: 'Single Sign-On (SAML/Okta)',
          priority_recommendation: 'high',
          complexity: 'moderate',
          required_department: 'Tier 2 Identity Support',
          confidence_score: 0.94,
          rationale: 'User cannot access corporate portal due to 403 Forbidden after credential reset.'
        });
        showToast('ℹ️ Standalone Dev Preview generated.', 'info');
      } else {
        showErrorBanner('Classification Failed', err.message || 'Could not classify ticket.');
      }
    } finally {
      btnClassify.disabled = false;
      btnClassify.innerHTML = '<span class="btn-icon">🏷️</span> Classify Ticket';
      autoAdjustHeight();
    }
  });

  function renderClassification(data) {
    triageCategory.textContent = data.category || 'General';
    triageSubcategory.textContent = data.subcategory || 'N/A';
    triagePriority.textContent = (data.priority_recommendation || 'normal').toUpperCase();
    triagePriority.className = `priority-pill priority-${(data.priority_recommendation || 'normal').toLowerCase()}`;
    triageComplexity.textContent = data.complexity || 'standard';
    triageDepartment.textContent = data.required_department || 'Customer Support';
    const conf = Math.round((data.confidence_score || 0.85) * 100);
    triageConfidence.textContent = `${conf}%`;
    triageRationale.textContent = data.rationale || '';
    triageResults.style.display = 'block';
  }

  // =========================================================================
  // VIEW 5: Sentiment & Frustration Radar
  // =========================================================================
  btnAnalyzeSentiment?.addEventListener('click', async () => {
    hideErrorBanner();
    btnAnalyzeSentiment.disabled = true;
    btnAnalyzeSentiment.innerHTML = '<span class="btn-spinner"></span> Analyzing Sentiment...';

    try {
      const resp = await fetch(`${backendUrl}/api/tickets/${currentTicketId}/sentiment`, {
        method: 'POST',
      });

      let data;
      if (resp.ok) {
        data = await resp.json();
      } else {
        throw new Error(`Sentiment error: ${resp.statusText}`);
      }

      renderRadar(data);
      showToast('📊 Sentiment & Frustration Radar updated!', 'success');
    } catch (err) {
      console.warn('Sentiment error:', err);
      if (!client) {
        renderRadar({
          sentiment: 'frustrated',
          frustration_level: 'High',
          churn_risk: 'Medium',
          unresolved_concerns: ['Unable to access portal for over 4 hours', 'Repeated login failure across browsers'],
          explanation: 'Customer is blocked from essential work tasks following an internal password update.'
        });
        showToast('ℹ️ Standalone Dev Preview generated.', 'info');
      } else {
        showErrorBanner('Radar Failed', err.message || 'Could not analyze sentiment.');
      }
    } finally {
      btnAnalyzeSentiment.disabled = false;
      btnAnalyzeSentiment.innerHTML = '<span class="btn-icon">📊</span> Run Sentiment Analysis';
      autoAdjustHeight();
    }
  });

  function renderRadar(data) {
    radarSentiment.textContent = getSentimentBadge(data.sentiment);
    radarFrustration.textContent = data.frustration_level || 'Moderate';
    radarChurn.textContent = `${data.churn_risk || 'Low'} Churn Risk`;
    radarChurn.className = `churn-pill churn-${(data.churn_risk || 'low').toLowerCase()}`;

    radarConcerns.innerHTML = '';
    const concerns = data.unresolved_concerns || [];
    if (concerns.length === 0) {
      radarConcerns.innerHTML = '<li>None identified</li>';
    } else {
      concerns.forEach((c) => {
        const li = document.createElement('li');
        li.textContent = c;
        radarConcerns.appendChild(li);
      });
    }

    radarExplanation.textContent = data.explanation || '';
    radarResults.style.display = 'block';
  }

  // =========================================================================
  // VIEW 6: Escalation Brief
  // =========================================================================
  btnGenEscalation?.addEventListener('click', async () => {
    hideErrorBanner();
    btnGenEscalation.disabled = true;
    btnGenEscalation.innerHTML = '<span class="btn-spinner"></span> Generating Brief...';

    try {
      const resp = await fetch(`${backendUrl}/api/tickets/${currentTicketId}/escalation-brief`, {
        method: 'POST',
      });

      let data;
      if (resp.ok) {
        data = await resp.json();
      } else {
        throw new Error(`Escalation error: ${resp.statusText}`);
      }

      escalationTextarea.value = data.markdown_brief || '';
      escalationResults.style.display = 'block';
      showToast('🚨 Escalation brief generated!', 'success');
    } catch (err) {
      console.warn('Escalation error:', err);
      if (!client) {
        escalationTextarea.value = `### 🚨 Engineering Escalation Brief\n\n**Issue Summary:** SSO Authentication failure resulting in 403 Forbidden for corporate user.\n**Business Impact:** User completely blocked from administrative portal.\n**Investigation Completed:** Checked client cookies, validated Okta directory sync.\n**Requested Action:** Tier 3 IAM engineer to inspect SAML certificate expiry on active tenant.`;
        escalationResults.style.display = 'block';
        showToast('ℹ️ Standalone Dev Preview generated.', 'info');
      } else {
        showErrorBanner('Escalation Failed', err.message || 'Could not generate brief.');
      }
    } finally {
      btnGenEscalation.disabled = false;
      btnGenEscalation.innerHTML = '<span class="btn-icon">🚨</span> Generate Escalation Brief';
      autoAdjustHeight();
    }
  });

  btnCopyEscalation?.addEventListener('click', async () => {
    const text = escalationTextarea.value;
    if (!text) return;
    await copyText(text);
    showToast('📋 Copied escalation brief!', 'success');
  });

  // =========================================================================
  // VIEW 7: Shift Handover Note
  // =========================================================================
  btnGenHandover?.addEventListener('click', async () => {
    hideErrorBanner();
    btnGenHandover.disabled = true;
    btnGenHandover.innerHTML = '<span class="btn-spinner"></span> Preparing Handover...';

    try {
      const resp = await fetch(`${backendUrl}/api/tickets/${currentTicketId}/shift-handover`, {
        method: 'POST',
      });

      let data;
      if (resp.ok) {
        data = await resp.json();
      } else {
        throw new Error(`Handover error: ${resp.statusText}`);
      }

      handoverTextarea.value = data.markdown_handover || '';
      handoverResults.style.display = 'block';
      showToast('📋 Shift handover note generated!', 'success');
    } catch (err) {
      console.warn('Handover error:', err);
      if (!client) {
        handoverTextarea.value = `### 📋 Shift Handover Note\n\n**Current State:** Awaiting customer confirmation after password re-sync.\n**Actions Taken:** Identity verified; certificate refreshed in IAM console.\n**Next Agent Action:** If customer has not confirmed access in 2 hours, send direct reset link.\n**Customer Commitment:** Follow up promised by 17:00 UTC.`;
        handoverResults.style.display = 'block';
        showToast('ℹ️ Standalone Dev Preview generated.', 'info');
      } else {
        showErrorBanner('Handover Failed', err.message || 'Could not generate handover note.');
      }
    } finally {
      btnGenHandover.disabled = false;
      btnGenHandover.innerHTML = '<span class="btn-icon">📋</span> Generate Shift Handover Note';
      autoAdjustHeight();
    }
  });

  btnCopyHandover?.addEventListener('click', async () => {
    const text = handoverTextarea.value;
    if (!text) return;
    await copyText(text);
    showToast('📋 Copied handover note!', 'success');
  });

  btnPostHandover?.addEventListener('click', () => {
    const noteText = handoverTextarea.value;
    if (!noteText) {
      showToast('⚠️ Handover note is empty.', 'warning');
      return;
    }
    openConfirmModal(
      'Confirm Handover Note Publication',
      `Post this Shift Handover note as an internal note on ticket #${currentTicketId}?`,
      () => executePostNote(noteText)
    );
  });

  // =========================================================================
  // VIEW 8: Knowledge Base Recommendations
  // =========================================================================
  btnFetchKb?.addEventListener('click', async () => {
    hideErrorBanner();
    btnFetchKb.disabled = true;
    btnFetchKb.innerHTML = '<span class="btn-spinner"></span> Searching Articles...';

    try {
      const resp = await fetch(`${backendUrl}/api/tickets/${currentTicketId}/knowledge-base`);
      let data;
      if (resp.ok) {
        data = await resp.json();
      } else {
        throw new Error(`KB error: ${resp.statusText}`);
      }

      renderKbResults(data.articles || []);
      showToast('📚 Relevant Knowledge Base articles retrieved!', 'success');
    } catch (err) {
      console.warn('KB error:', err);
      if (!client) {
        renderKbResults([
          {
            title: 'Troubleshooting Okta Single Sign-On 403 Forbidden Errors',
            url: 'https://support.example.com/hc/en-us/articles/360012345678',
            snippet: 'Learn how to resolve common SAML 2.0 permission errors and certificate expiry mismatches.',
            relevance_explanation: 'Directly explains the 403 Forbidden symptom following corporate credential reset.'
          },
          {
            title: 'Configuring SCIM Group Synchronization in Active Directory',
            url: 'https://support.example.com/hc/en-us/articles/360087654321',
            snippet: 'Guide to ensuring group memberships synchronize without delay during password renewals.',
            relevance_explanation: 'Provides root cause resolution steps for user permission group de-sync.'
          }
        ]);
        showToast('ℹ️ Standalone Dev Preview generated.', 'info');
      } else {
        showErrorBanner('Search Failed', err.message || 'Could not retrieve articles.');
      }
    } finally {
      btnFetchKb.disabled = false;
      btnFetchKb.innerHTML = '<span class="btn-icon">📚</span> Search Knowledge Base';
      autoAdjustHeight();
    }
  });

  function renderKbResults(articles) {
    kbArticleList.innerHTML = '';
    if (articles.length === 0) {
      kbArticleList.innerHTML = '<p class="history-empty">No matching articles found in Help Center.</p>';
    } else {
      articles.forEach((art) => {
        const item = document.createElement('div');
        item.className = 'kb-item';
        item.innerHTML = `
          <a class="kb-link" href="${escapeHtml(art.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(art.title)}</a>
          <p class="kb-snippet">${escapeHtml(art.snippet || '')}</p>
          <p class="kb-relevance">💡 <em>${escapeHtml(art.relevance_explanation || 'Relevant article')}</em></p>
        `;
        kbArticleList.appendChild(item);
      });
    }
    kbResults.style.display = 'block';
  }

  // =========================================================================
  // VIEW 9: Similar & Duplicate Ticket Discovery
  // =========================================================================
  btnFetchSimilar?.addEventListener('click', async () => {
    hideErrorBanner();
    btnFetchSimilar.disabled = true;
    btnFetchSimilar.innerHTML = '<span class="btn-spinner"></span> Scanning Tickets...';

    try {
      const resp = await fetch(`${backendUrl}/api/tickets/${currentTicketId}/similar-tickets`);
      let data;
      if (resp.ok) {
        data = await resp.json();
      } else {
        throw new Error(`Similar tickets error: ${resp.statusText}`);
      }

      renderSimilarResults(data.similar_tickets || []);
      showToast('🔗 Similar tickets retrieved!', 'success');
    } catch (err) {
      console.warn('Similar tickets error:', err);
      if (!client) {
        renderSimilarResults([
          {
            ticket_id: 842,
            subject: 'User locked out with 403 Forbidden after SSO migration',
            status: 'solved',
            similarity_score: 0.92,
            matching_reasons: ['Same 403 Forbidden error', 'SAML SSO post-password change'],
            resolution_summary: 'Refreshed SAML signing certificate in tenant IAM settings.',
            is_potential_duplicate: false
          },
          {
            ticket_id: 1000,
            subject: 'Alex Rivera SSO Login Failure',
            status: 'open',
            similarity_score: 0.98,
            matching_reasons: ['Same requester Alex Rivera', 'Created within 15 minutes of #1001'],
            resolution_summary: 'Pending triage',
            is_potential_duplicate: true
          }
        ]);
        showToast('ℹ️ Standalone Dev Preview generated.', 'info');
      } else {
        showErrorBanner('Search Failed', err.message || 'Could not search similar tickets.');
      }
    } finally {
      btnFetchSimilar.disabled = false;
      btnFetchSimilar.innerHTML = '<span class="btn-icon">🔗</span> Find Similar Tickets';
      autoAdjustHeight();
    }
  });

  function renderSimilarResults(tickets) {
    similarTicketList.innerHTML = '';
    if (tickets.length === 0) {
      similarTicketList.innerHTML = '<p class="history-empty">No similar tickets found.</p>';
    } else {
      tickets.forEach((t) => {
        const item = document.createElement('div');
        item.className = 'similar-item';
        const isDup = t.is_potential_duplicate;
        item.innerHTML = `
          <div class="similar-header">
            <strong>Ticket #${t.ticket_id}: ${escapeHtml(t.subject)}</strong>
            ${isDup ? '<span class="duplicate-badge">⚠️ Potential Duplicate</span>' : ''}
          </div>
          <div class="similar-meta">
            <span>Status: <strong>${t.status || 'solved'}</strong></span>
            <span>Match: <strong>${Math.round((t.similarity_score || 0.8) * 100)}%</strong></span>
          </div>
          <p class="similar-reasons"><strong>Matching Reasons:</strong> ${(t.matching_reasons || []).map(escapeHtml).join(', ')}</p>
          ${t.resolution_summary ? `<p class="similar-resolution"><strong>Past Resolution:</strong> ${escapeHtml(t.resolution_summary)}</p>` : ''}
        `;
        similarTicketList.appendChild(item);
      });
    }
    similarResults.style.display = 'block';
  }

  // =========================================================================
  // Confirmation Modal
  // =========================================================================
  function openConfirmModal(title, description, onConfirm) {
    modalTitle.textContent = title;
    modalDesc.textContent = description;
    pendingConfirmAction = onConfirm;
    confirmModal.style.display = 'flex';
  }

  function closeConfirmModal() {
    confirmModal.style.display = 'none';
    pendingConfirmAction = null;
  }

  btnModalCancel?.addEventListener('click', closeConfirmModal);
  btnModalConfirm?.addEventListener('click', () => {
    const action = pendingConfirmAction;
    closeConfirmModal();
    if (typeof action === 'function') {
      action();
    }
  });

  // =========================================================================
  // Helper Utilities
  // =========================================================================
  errorCloseBtn?.addEventListener('click', hideErrorBanner);

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

  async function copyText(text) {
    try {
      await navigator.clipboard.writeText(text);
    } catch (e) {
      const textarea = document.createElement('textarea');
      textarea.value = text;
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand('copy');
      document.body.removeChild(textarea);
    }
  }

  function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  function setLoadingState(isLoading) {
    if (!btnSummarize) return;
    btnSummarize.disabled = isLoading;
    if (isLoading) {
      if (summarizeSpinner) summarizeSpinner.style.display = 'inline-block';
      if (summarizeIcon) summarizeIcon.style.display = 'none';
      if (btnSummarizeText) btnSummarizeText.textContent = 'Analyzing Ticket...';
      if (skeletonContainer) skeletonContainer.style.display = 'flex';
      if (summarySection) summarySection.style.display = 'none';
    } else {
      if (summarizeSpinner) summarizeSpinner.style.display = 'none';
      if (summarizeIcon) summarizeIcon.style.display = 'inline';
      if (btnSummarizeText) btnSummarizeText.textContent = 'Generate AI Summary';
      if (skeletonContainer) skeletonContainer.style.display = 'none';
    }
  }

  function setPostingState(isPosting) {
    if (!btnPostDirect) return;
    btnPostDirect.disabled = isPosting;
    if (isPosting) {
      if (postSpinner) postSpinner.style.display = 'inline-block';
      if (postIcon) postIcon.style.display = 'none';
      if (postText) postText.textContent = 'Posting Note...';
    } else {
      if (postSpinner) postSpinner.style.display = 'none';
      if (postIcon) postIcon.style.display = 'inline';
      if (postText) postText.textContent = 'Post as Internal Note';
    }
  }

  function showToast(message, type = 'info') {
    if (!toast || !toastMessage || !toastIcon) return;
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
    const bodyHeight = Math.min(Math.max(document.body.scrollHeight + 24, 380), 800);
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
