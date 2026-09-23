import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { getRoles } from '../api/apiClient';
import { useStore } from '../store/useStore';
import { User } from 'lucide-react';

const RoleSelection: React.FC = () => {
  const [roles, setRoles] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();
  const { topic, setRole } = useStore();

  useEffect(() => {
    if (!topic) {
      navigate('/topics');
      return;
    }

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
  }, [topic, navigate]);

  const handleSelectRole = (role: any) => {
    setRole(role);
    navigate('/scenario');
  };

  if (loading) {
    return <div className="min-h-screen flex items-center justify-center">Loading roles...</div>;
  }

  return (
    <div className="min-h-screen p-8 md:p-16 max-w-7xl mx-auto">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="mb-12"
      >
        <h1 className="text-3xl md:text-5xl font-bold mb-4">Select a Persona</h1>
        <p className="text-slate-600 text-lg">Who do you want to talk to for your <span className="text-slate-900 font-medium">{topic?.title}</span>?</p>
      </motion.div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {roles.map((role, index) => (
          <motion.div
            key={role.id}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: index * 0.1 }}
            onClick={() => handleSelectRole(role)}
            className="glass-card p-6 rounded-2xl cursor-pointer hover:border-[var(--color-primary)] transition-all"
          >
            <div className="flex items-center gap-4 mb-4">
              <div className="w-14 h-14 rounded-full bg-[var(--color-surface)] border border-slate-200 flex items-center justify-center">
                <User size={24} className="text-slate-600" />
              </div>
              <div>
                <h3 className="text-xl font-bold">{role.name}</h3>
              </div>
            </div>
            <p className="text-sm text-slate-600 mb-4 h-10">{role.description}</p>
            
            <div className="flex flex-wrap gap-2">
              {role.traits.map((trait: string) => (
                <span key={trait} className="px-2 py-1 text-xs rounded-full bg-slate-50 border border-slate-200 text-slate-600">
                  {trait}
                </span>
              ))}
            </div>
          </motion.div>
        ))}
      </div>
    </div>
  );
};

export default RoleSelection;
