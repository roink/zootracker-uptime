import React from 'react';
import { Link } from 'react-router-dom';

// Simple footer matching the header color and linking to legal pages.
export default function Footer() {
  return (
    <footer className="navbar navbar-dark bg-success mt-4">
      <div className="container-fluid justify-content-center">
        <Link className="nav-link footer-link" to="/impress">
          Impress
        </Link>
        <span className="text-white mx-2">|</span>
        <Link className="nav-link footer-link" to="/data-protection">
          Data Protection
        </Link>
        <span className="text-white mx-2">|</span>
        <Link className="nav-link footer-link" to="/contact">
          Contact
        </Link>
      </div>
    </footer>
  );
}
