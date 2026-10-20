using Hellcat.Sim;

namespace Hellcat.Game.World
{
    /// <summary>A scene object that adds its own soft bodies (debris, props) to the world before it is built; they share
    /// the solver with the car (D-081). Called again when the world is rebuilt (F9), so keep only the indices it returns.</summary>
    public interface IDynamicBodySource
    {
        void AddBodies(SoftBodyWorld world);
    }
}
