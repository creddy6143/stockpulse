import { initializeApp } from "firebase/app";
import { getAuth, GoogleAuthProvider } from "firebase/auth";

const firebaseConfig = {
  apiKey: "AIzaSyDYeaNL2cEjlq7pbze5eQRBH5aFceoHdB4",
  authDomain: "stockpulse-2aa43.firebaseapp.com",
  projectId: "stockpulse-2aa43",
  storageBucket: "stockpulse-2aa43.firebasestorage.app",
  messagingSenderId: "369404858187",
  appId: "1:369404858187:web:429543ef768e94c67122ce",
  measurementId: "G-TLBCDW2Z76",
};

const app = initializeApp(firebaseConfig);
export const auth = getAuth(app);
export const googleProvider = new GoogleAuthProvider();
