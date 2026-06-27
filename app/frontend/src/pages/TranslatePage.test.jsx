import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { SettingsProvider } from '../contexts/SettingsContext.jsx';
import TranslatePage from './TranslatePage.jsx';
import { createJob } from '../api/jobs.js';

// ---------------------------------------------------------------------------
// Mock all modules that make network calls
// ---------------------------------------------------------------------------

vi.mock('../api/jobs.js', () => ({
  createJob: vi.fn().mockResolvedValue({ job_id: 'test-job-123' }),
  cancelJob: vi.fn().mockResolvedValue({}),
  getJudge: vi.fn().mockResolvedValue(null),
  fetchJobStatus: vi.fn().mockResolvedValue({ status: 'pending' }),
  fetchJobQuality: vi.fn().mockResolvedValue({}),
  applyJudge: vi.fn().mockResolvedValue({}),
}));

vi.mock('../api/config.js', () => ({
  fetchProfiles: vi.fn().mockResolvedValue([
    { id: 'general', name: 'General', description: '通用翻譯' },
  ]),
  fetchModelConfig: vi.fn().mockResolvedValue([]),
  fetchRouteInfo: vi.fn().mockResolvedValue({ routes: [] }),
}));

// Prevent the polling hook from starting intervals during tests
vi.mock('../hooks/useJobPolling.js', () => ({
  useJobPolling: vi.fn(),
}));

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function renderApp() {
  return render(
    <SettingsProvider>
      <TranslatePage />
    </SettingsProvider>
  );
}

/**
 * Navigate from the initial step 1 to step 2 by simulating a file upload
 * and clicking the "下一步" button.
 */
function navigateToStep2() {
  const fileInput = document.querySelector('input[type="file"]');
  const file = new File(['content'], 'test.docx', { type: 'application/octet-stream' });
  // Override the read-only `files` property on the input element so the
  // onChange handler receives a usable file list.
  Object.defineProperty(fileInput, 'files', { value: [file], configurable: true });
  fireEvent.change(fileInput);
  // After the ADD_FILES dispatch, files.length > 0, enabling the button.
  fireEvent.click(screen.getByText('下一步'));
}

// ---------------------------------------------------------------------------
// Reset between tests
// ---------------------------------------------------------------------------

beforeEach(() => {
  localStorage.clear();
  vi.clearAllMocks();
});

// ---------------------------------------------------------------------------
// Tests (names match test-plan.md exactly)
// ---------------------------------------------------------------------------

test('test_output_mode_selector_renders_both_labeled_options', () => {
  renderApp();
  navigateToStep2();

  // The output-mode Select defaults to 'append' → displayed as '原文在下方'
  const select = screen.getByDisplayValue('原文在下方');
  const options = select.querySelectorAll('option');

  expect(options.length).toBe(2);
  expect(options[0].value).toBe('append');
  expect(options[0].textContent).toBe('原文在下方');
  expect(options[1].value).toBe('replace');
  expect(options[1].textContent).toBe('原地取代/覆蓋原文');
});

test('test_output_mode_default_value_is_append', () => {
  renderApp();
  navigateToStep2();

  const select = screen.getByDisplayValue('原文在下方');
  expect(select.value).toBe('append');
});

test('test_output_mode_replace_appends_field_to_form_data', async () => {
  renderApp();
  navigateToStep2();

  // Change output mode to 'replace'
  const select = screen.getByDisplayValue('原文在下方');
  fireEvent.change(select, { target: { value: 'replace' } });

  // Select at least one target language so the submit button becomes enabled.
  // LanguageGrid checkboxes appear before the term-extraction checkbox in the DOM.
  const checkboxes = screen.getAllByRole('checkbox');
  fireEvent.click(checkboxes[0]);

  // Submit
  fireEvent.click(screen.getByText('開始翻譯'));

  // Wait for the async handleSubmit to call the mocked createJob
  await waitFor(() => expect(createJob).toHaveBeenCalledOnce());

  const formData = createJob.mock.calls[0][0];
  expect(formData.get('output_mode')).toBe('replace');
});
