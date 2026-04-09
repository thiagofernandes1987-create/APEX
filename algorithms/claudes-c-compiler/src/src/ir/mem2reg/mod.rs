pub(crate) mod promote;
pub(crate) mod phi_eliminate;

pub(crate) use promote::promote_allocas;
pub(crate) use promote::promote_allocas_with_params;
pub(crate) use phi_eliminate::eliminate_phis;
