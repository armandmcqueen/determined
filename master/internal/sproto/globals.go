package sproto

import (
	"fmt"
	"github.com/pkg/errors"

	"github.com/determined-ai/determined/master/pkg/actor"
)

var (
	// ResourceManagerAddr is the actor address of the resource manager router.
	ResourceManagerAddr = actor.Addr("resourceManagers")
	// AgentRMAddr is the actor address of the agent resource manager.
	AgentRMAddr = actor.Addr("agentRM")
	// K8sRMAddr is the actor address of the k8s resource manager.
	K8sRMAddr = actor.Addr("kubernetesRM")
	// AgentsAddr is the actor address of the agents.
	AgentsAddr = actor.Addr("agents")
	// PodsAddr is the actor address of the pods.
	PodsAddr = actor.Addr("pods")
)

type (
	// GetDefaultGPUResourcePoolReq is a message asking for the name of the default GPU resource pool
	GetDefaultGPUResourcePoolReq struct{}

	// GetDefaultGPUResourcePoolResponse is the response to GetDefaultGPUResourcePoolReq
	GetDefaultGPUResourcePoolResponse struct {
		PoolName string
	}

	// GetDefaultCPUResourcePoolReq is a message asking for the name of the default CPU resource pool
	GetDefaultCPUResourcePoolReq struct{}

	// GetDefaultCPUResourcePoolResponse is the response to GetDefaultCPUResourcePoolReq
	GetDefaultCPUResourcePoolResponse struct {
		PoolName string
	}
)

// GetRM returns the resource manager router.
func GetRM(system *actor.System) *actor.Ref {
	return system.Get(ResourceManagerAddr)
}

// UseAgentRM returns if using the agent resource manager.
func UseAgentRM(system *actor.System) bool {
	return system.Get(AgentsAddr) != nil
}

// UseK8sRM returns if using the kubernetes resource manager.
func UseK8sRM(system *actor.System) bool {
	return system.Get(PodsAddr) != nil
}

// GetRP returns the resource pool.
func GetRP(system *actor.System, name string) *actor.Ref {
	if rm := system.Get(AgentRMAddr); rm != nil {
		return rm.Child(name)
	}
	return nil
}

// GetDefaultGPUResourcePool returns the default GPU resource pool
func GetDefaultGPUResourcePool(system *actor.System) string {
	rm := GetRM(system)
	fmt.Printf("RM %s", rm)
	fut := system.Ask(rm, GetDefaultGPUResourcePoolReq{})
	fmt.Printf("Future %s", fut)
	resp := fut.Get()
	fmt.Printf("resp %s", resp)
	return resp.(GetDefaultGPUResourcePoolResponse).PoolName
}

// GetDefaultCPUResourcePool returns the default CPU resource pool
func GetDefaultCPUResourcePool(system *actor.System) string {
	resp := system.Ask(GetRM(system), GetDefaultCPUResourcePoolReq{}).Get()
	return resp.(GetDefaultCPUResourcePoolResponse).PoolName
}

// ValidateRP validates if the resource pool exists when using the agent resource manager.
func ValidateRP(system *actor.System, name string) error {
	if name == "" || UseAgentRM(system) && GetRP(system, name) != nil {
		return nil
	}
	return errors.Errorf("cannot find resource pool: %s", name)
}
