'use client';

import { useState, useEffect } from 'react';
import { api } from '@/lib/api';
import { storage } from '@/lib/storage';
import Link from 'next/link';

export default function ProfilePage() {
  const [apiKey, setApiKey] = useState('');
  const [isVerified, setIsVerified] = useState(false);
  const [verifying, setVerifying] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [savedKey, setSavedKey] = useState<string | null>(null);

  useEffect(() => {
    const existingKey = storage.getGroqKey();
    const verified = storage.isKeyVerified();
    if (existingKey) {
      setSavedKey(storage.getMaskedKey());
      setIsVerified(verified);
    }
  }, []);

  const handleVerify = async () => {
    if (!apiKey.trim()) {
      setMessage({ type: 'error', text: 'Please enter an API key' });
      return;
    }
    setVerifying(true);
    setMessage(null);
    try {
      const response = await api.verifyApiKey({ apiKey: apiKey.trim() });
      if (response.ok) {
        storage.setGroqKey(apiKey.trim());
        storage.setKeyVerified(true);
        setSavedKey(storage.getMaskedKey());
        setIsVerified(true);
        setApiKey('');
        setMessage({ type: 'success', text: 'API key verified and saved!' });
      } else {
        setMessage({ type: 'error', text: response.message || 'Verification failed' });
        storage.setKeyVerified(false);
      }
    } catch (err: any) {
      setMessage({ type: 'error', text: err.message || 'Failed to verify API key' });
      storage.setKeyVerified(false);
    } finally {
      setVerifying(false);
    }
  };

  const handleRemoveKey = () => {
    storage.removeGroqKey();
    setSavedKey(null);
    setIsVerified(false);
    setApiKey('');
    setMessage({ type: 'success', text: 'API key removed' });
  };

  return (
    <div className="min-h-screen bg-[#FAFAFA]">
      <div className="max-w-lg mx-auto px-4 sm:px-6 py-8">
        <div className="mb-6">
          <Link href="/courses" className="inline-flex items-center text-sm text-[#8A8690] hover:text-[#3B82F6] font-medium transition-colors">
            <svg className="w-4 h-4 mr-1.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
            Back to Courses
          </Link>
        </div>

        <div className="bg-white rounded-xl border border-[#E2E5F1] p-6">
          <h1 className="text-lg font-bold text-[#1A1A2E] mb-1" style={{ fontFamily: 'Red Hat Display, sans-serif' }}>Settings</h1>
          <p className="text-sm text-[#8A8690] mb-6">Configure your API key to use Codebasics Chat Buddy.</p>

          {savedKey && (
            <div className="mb-5 p-4 bg-[#FAFAFA] rounded-lg border border-[#E2E5F1]">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-[11px] font-medium text-[#8A8690] uppercase tracking-wider mb-1">Current API Key</p>
                  <p className="font-mono text-sm text-[#1A1A2E]">{savedKey}</p>
                </div>
                <div className="flex items-center gap-2">
                  <span className={`inline-flex items-center px-2 py-0.5 rounded-md text-[11px] font-medium ${isVerified ? 'bg-[#ECFDF5] text-[#059669] border border-[#A7F3D0]' : 'bg-[#EFF6FF] text-[#3B82F6] border border-[#3B82F6]/20'}`}>
                    {isVerified ? 'Verified' : 'Unverified'}
                  </span>
                  <button onClick={handleRemoveKey} className="text-xs text-[#EF4444] hover:text-[#DC2626] font-medium transition-colors">Remove</button>
                </div>
              </div>
            </div>
          )}

          <div className="space-y-3">
            <div>
              <label htmlFor="apiKey" className="block text-xs font-medium text-[#1A1A2E] mb-1.5">Groq API Key</label>
              <input id="apiKey" type="password" value={apiKey} onChange={(e) => setApiKey(e.target.value)} placeholder="gsk_..." className="w-full px-3.5 py-2.5 bg-[#FAFAFA] border border-[#E2E5F1] rounded-lg focus:outline-none focus:border-[#3B82F6]/40 focus:bg-white transition-all text-sm placeholder-[#8A8690]" onKeyDown={(e) => e.key === 'Enter' && handleVerify()} />
              <p className="mt-1.5 text-xs text-[#8A8690]">Get your key from{' '}<a href="https://console.groq.com/keys" target="_blank" rel="noopener noreferrer" className="text-[#3B82F6] hover:underline">console.groq.com</a></p>
            </div>
            <button onClick={handleVerify} disabled={verifying || !apiKey.trim()} className="w-full bg-[#3B82F6] hover:bg-[#2563EB] text-white px-4 py-2.5 rounded-lg disabled:bg-[#E2E5F1] disabled:text-[#8A8690] disabled:cursor-not-allowed transition-colors text-sm font-medium">
              {verifying ? 'Verifying...' : 'Save & Verify'}
            </button>
            {message && (
              <div className={`p-3 rounded-lg text-sm ${message.type === 'success' ? 'bg-[#ECFDF5] text-[#059669] border border-[#A7F3D0]' : 'bg-[#FEF2F2] text-[#DC2626] border border-[#FECACA]'}`}>{message.text}</div>
            )}
          </div>

          <div className="mt-6 p-4 bg-[#EFF6FF] rounded-lg border border-[#DBEAFE]">
            <p className="text-xs font-medium text-[#1A1A2E] mb-2">About your API key</p>
            <ul className="text-xs text-[#8A8690] space-y-1.5">
              <li className="flex items-start gap-2"><svg className="w-3.5 h-3.5 text-[#3B82F6] flex-shrink-0 mt-0.5" fill="currentColor" viewBox="0 0 20 20"><path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" /></svg>Stored locally in your browser only</li>
              <li className="flex items-start gap-2"><svg className="w-3.5 h-3.5 text-[#3B82F6] flex-shrink-0 mt-0.5" fill="currentColor" viewBox="0 0 20 20"><path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" /></svg>Never sent to our servers or logged</li>
              <li className="flex items-start gap-2"><svg className="w-3.5 h-3.5 text-[#3B82F6] flex-shrink-0 mt-0.5" fill="currentColor" viewBox="0 0 20 20"><path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" /></svg>You can remove it at any time</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}
