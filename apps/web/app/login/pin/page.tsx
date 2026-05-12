"use client";

import { useState } from 'react';
import { useRouter } from 'next/navigation';

export default function PinLoginPage() {
  const [pin, setPin] = useState('');
  const [error, setError] = useState('');
  const router = useRouter();

  const handlePinSubmit = async () => {
    if (pin.length !== 4) {
      setError('PIN must be 4 digits');
      return;
    }

    // TODO: Validate PIN with backend
    console.log('PIN entered:', pin);
    router.push('/');
  };

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      <div className="flex-1 flex items-center justify-center p-8">
        <div className="max-w-sm w-full">
          <div className="text-center mb-8">
            <div className="mx-auto w-16 h-16 bg-blue-100 rounded-2xl flex items-center justify-center mb-4">
              <span className="text-3xl">🔒</span>
            </div>
            <h1 className="text-2xl font-semibold text-gray-900">Enter PIN</h1>
            <p className="text-gray-600 mt-2">Tap to unlock viewer mode</p>
          </div>

          <div className="bg-white rounded-3xl p-8 shadow-sm">
            <div className="flex justify-center gap-3 mb-8">
              {[0,1,2,3].map((i) => (
                <div key={i} className={`w-4 h-4 rounded-full ${pin.length > i ? 'bg-blue-600' : 'bg-gray-200'}`} />
              ))}
            </div>

            <div className="grid grid-cols-3 gap-4">
              {[1,2,3,4,5,6,7,8,9,'',0,'⌫'].map((num, index) => (
                <button
                  key={index}
                  onClick={() => {
                    if (num === '⌫') {
                      setPin(pin.slice(0, -1));
                    } else if (typeof num === 'number' && pin.length < 4) {
                      setPin(pin + num);
                    }
                  }}
                  className="h-16 flex items-center justify-center text-2xl font-medium bg-gray-100 active:bg-gray-200 rounded-2xl transition-colors"
                >
                  {num}
                </button>
              ))}
            </div>
          </div>

          <div className="mt-6 text-center">
            <button
              onClick={() => router.push('/login')}
              className="text-blue-600 text-sm hover:underline"
            >
              Sign in with email instead
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}