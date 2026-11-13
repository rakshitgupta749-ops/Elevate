import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { getRoles } from '../api/apiClient';
import { useStore } from '../store/useStore';
import { User, ArrowLeft } from 'lucide-react';

const RoleSelection: React.FC = () => {
  const [roles, setRoles] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();
  const { setRole } = useStore();

  useEffect(() => {
    const fetchRoles = async () => {
      try {
        const data = await getRoles();
        setRoles(data);
      } catch (error) {
        console.error('Failed to fetch roles', error);
      } finally {
        setLoading(false);
      }
    };
    fetchRoles();
  }, []);

  const handleSelectRole = (role: any) => {
    setRole(role);
    navigate('/scenario');
  };

  if (loading) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center text-slate-400 bg-transparent">
        <div className="w-8 h-8 border-2 border-teal-500 border-t-transparent rounded-full animate-spin mb-3" />
        <span className="text-sm font-medium">Loading executive personas...</span>
      </div>
    );
  }

  return (
    <div className="min-h-screen p-6 md:p-12 lg:p-16 max-w-7xl mx-auto text-slate-100 bg-transparent relative z-10">
      <div className="mb-8">
        <button
          onClick={() => navigate('/')}
          className="inline-flex items-center gap-2 text-xs font-semibold text-slate-300 hover:text-white px-3.5 py-2 rounded-xl bg-slate-900/80 hover:bg-slate-800 border border-slate-700/80 shadow-md backdrop-blur-md transition-colors cursor-pointer"
        >
          <ArrowLeft size={14} /> Back to Home
        </button>
      </div>

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="mb-10"
      >
        <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-teal-500/10 border border-teal-500/20 text-teal-400 text-xs font-semibold uppercase tracking-wider mb-2">
          <User size={13} />
          <span>Stage 1 • Executive Counterpart Persona</span>
        </div>
        <h1 className="text-3xl md:text-5xl font-extrabold tracking-tight text-white mb-3">
          Select a Persona
        </h1>
        <p className="text-slate-400 text-base md:text-lg max-w-2xl leading-relaxed">
          Choose the executive stakeholder persona you want to practice with.
        </p>
      </motion.div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {roles.map((role, index) => (
          <motion.div
            key={role.id}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: index * 0.1 }}
            onClick={() => handleSelectRole(role)}
            className="bg-slate-900/75 hover:bg-slate-850/90 border border-slate-800 hover:border-teal-500/60 p-6 rounded-2xl cursor-pointer group flex flex-col h-full backdrop-blur-md transition-all duration-300 shadow-xl hover:shadow-teal-500/10 hover:-translate-y-1"
          >
            <div className="flex items-center gap-4 mb-4">
              <div className="w-14 h-14 rounded-2xl bg-gradient-to-tr from-slate-800 to-slate-700/80 border border-slate-700/80 flex items-center justify-center text-teal-400 group-hover:from-teal-600 group-hover:to-teal-500 group-hover:text-white group-hover:border-teal-400 transition-all shadow-md shrink-0">
                <User size={24} />
              </div>
              <div>
                <h3 className="text-xl font-bold text-white group-hover:text-teal-200 transition-colors">
                  {role.name}
                </h3>
                <span className="text-[11px] text-teal-400/90 font-medium tracking-wide uppercase">
                  Executive Counterpart
                </span>
              </div>
            </div>
            
            <p className="text-sm text-slate-400 mb-5 leading-relaxed min-h-[48px]">
              {role.description}
            </p>
            
            <div className="flex flex-wrap gap-2 mb-4">
              {role.traits.map((trait: string) => (
                <span key={trait} className="px-2.5 py-1 text-xs font-medium rounded-lg bg-slate-800/80 border border-slate-700/70 text-slate-300 group-hover:border-slate-600">
                  {trait}
                </span>
              ))}
            </div>

            <div className="mt-auto pt-4 border-t border-slate-800/80 flex items-center justify-between text-xs text-teal-400 font-semibold group-hover:text-teal-300">
              <span>Select persona</span>
              <span className="group-hover:translate-x-1 transition-transform">→</span>
            </div>
          </motion.div>
        ))}
      </div>
    </div>
  );
};

export default RoleSelection;
